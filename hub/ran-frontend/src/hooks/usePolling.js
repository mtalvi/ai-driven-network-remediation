import { useEffect, useRef, useState } from "react";

const POLL_INTERVAL = 10_000;

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

    fetchData();
    const id = setInterval(fetchData, POLL_INTERVAL);

    return () => {
      activeRef.current = false;
      clearInterval(id);
    };
  }, [baseUrl]);

  return { anomalies, count, deps, loading, error, lastUpdated };
}
