import { useCallback, useEffect, useRef, useState } from "react";

const POLL_INTERVAL = 10_000;
// After a demo trigger, poll faster for a while so the anomaly table visibly
// updates soon after clicking, instead of waiting up to a full 10s cycle on
// top of the pipeline's own detection/RCA latency.
const FAST_POLL_INTERVAL = 4_000;
const FAST_POLL_DURATION = 75_000;

function extractDeps(data) {
  if (!data || !data._deps) return { status: "ok", unavailable: [] };
  return {
    status: data._deps.status || "ok",
    unavailable: data._deps.unavailable || [],
  };
}

export function usePolling(baseUrl) {
  const [anomalies, setAnomalies] = useState([]);
  const [count, setCount] = useState(0);
  const [deps, setDeps] = useState({ status: "ok", unavailable: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const activeRef = useRef(true);
  const fastUntilRef = useRef(0);
  const timeoutRef = useRef(null);
  const fetchDataRef = useRef(null);

  const speedUpPolling = useCallback((durationMs = FAST_POLL_DURATION) => {
    fastUntilRef.current = Date.now() + durationMs;
  }, []);

  // Lets callers (e.g. after a Clear or a demo trigger) force an immediate
  // fetch instead of waiting for the next scheduled poll tick.
  const refetchNow = useCallback(async () => {
    if (fetchDataRef.current) {
      await fetchDataRef.current();
    }
  }, []);

  useEffect(() => {
    activeRef.current = true;

    async function fetchData() {
      try {
        const base = baseUrl || "";
        const res = await fetch(`${base}/api/anomalies`);

        if (!res.ok) {
          throw new Error(`BFF responded with ${res.status}`);
        }

        const data = await res.json();

        if (activeRef.current) {
          setAnomalies(data.anomalies || []);
          setCount(data.count || 0);
          setDeps(extractDeps(data));
          setLastUpdated(new Date());
          setError(null);
        }
      } catch (err) {
        if (activeRef.current) {
          setError(err.message || "Failed to reach BFF");
        }
      } finally {
        if (activeRef.current) {
          setLoading(false);
        }
      }
    }

    fetchDataRef.current = fetchData;

    function scheduleNext() {
      const interval = Date.now() < fastUntilRef.current ? FAST_POLL_INTERVAL : POLL_INTERVAL;
      timeoutRef.current = setTimeout(async () => {
        await fetchData();
        if (activeRef.current) scheduleNext();
      }, interval);
    }

    fetchData().then(() => {
      if (activeRef.current) scheduleNext();
    });

    return () => {
      activeRef.current = false;
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [baseUrl]);

  return { anomalies, count, deps, loading, error, lastUpdated, speedUpPolling, refetchNow };
}
