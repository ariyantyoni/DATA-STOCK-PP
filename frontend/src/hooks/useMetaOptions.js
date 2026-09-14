import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";

export function useMetaOptions() {
  const [options, setOptions] = useState({});
  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/meta/options");
      setOptions(data);
    } catch {}
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  return { options, refresh };
}
