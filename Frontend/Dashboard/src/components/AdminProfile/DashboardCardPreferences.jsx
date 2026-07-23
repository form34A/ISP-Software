import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { LayoutDashboard, Eye } from 'lucide-react';
import { FaSpinner } from 'react-icons/fa';
import api from '../../api';
import { motion, AnimatePresence } from 'framer-motion';

const Switch = ({ checked, onChange, theme, label }) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    aria-label={label}
    onClick={onChange}
    className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors ${
      checked ? "bg-indigo-600" : theme === "dark" ? "bg-gray-600" : "bg-gray-300"
    }`}
  >
    <span
      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
        checked ? "translate-x-6" : "translate-x-1"
      }`}
    />
  </button>
);

const DashboardCardPreferences = ({ theme }) => {
  const [available, setAvailable] = useState([]);
  const [hidden, setHidden] = useState(() => new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Chains every PATCH after whatever's currently in flight, in order, so
  // rapid toggles can't race and have an earlier (slower) request resolve
  // after a later one and clobber it.
  const requestChainRef = useRef(Promise.resolve());

  const fetchPrefs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.get("/api/account/dashboard-preferences/");
      setAvailable(response.data?.available || []);
      setHidden(new Set(response.data?.hidden || []));
    } catch (err) {
      console.error("fetch dashboard preferences error", err);
      setError("Failed to load dashboard preferences.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPrefs();
  }, [fetchPrefs]);

  const savePrefs = useCallback((nextHidden) => {
    requestChainRef.current = requestChainRef.current
      .then(() => api.patch("/api/account/dashboard-preferences/", {
        hidden: Array.from(nextHidden),
      }))
      .catch((err) => {
        console.error("save dashboard preferences error", err);
        setError(err.response?.data?.detail || "Failed to save — change reverted.");
        // Revert only what this specific request tried to change, so any
        // other toggles applied (and already queued) since aren't undone.
        setHidden((current) => {
          const reverted = new Set(current);
          nextHidden.forEach((key) => {
            if (!reverted.has(key)) reverted.add(key);
          });
          current.forEach((key) => {
            if (!nextHidden.has(key)) reverted.delete(key);
          });
          return reverted;
        });
      });
  }, []);

  const toggleItem = useCallback((key) => {
    setHidden((prevHidden) => {
      const next = new Set(prevHidden);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      savePrefs(next);
      return next;
    });
    setError(null);
  }, [savePrefs]);

  const showAll = useCallback(() => {
    setHidden(new Set());
    savePrefs(new Set());
    setError(null);
  }, [savePrefs]);

  const groups = useMemo(() => {
    const order = [];
    const byGroup = new Map();
    available.forEach((item) => {
      if (!byGroup.has(item.group)) {
        byGroup.set(item.group, []);
        order.push(item.group);
      }
      byGroup.get(item.group).push(item);
    });
    return order.map((groupName) => ({ groupName, items: byGroup.get(groupName) }));
  }, [available]);

  const hiddenCount = hidden.size;

  return (
    <div className={`rounded-xl p-6 shadow-lg ${
      theme === "dark"
        ? "bg-gray-800/60 backdrop-blur-md text-white"
        : "bg-white/60 backdrop-blur-md text-gray-800"
    }`}>
      <div className="flex items-center justify-between flex-wrap gap-3 mb-2">
        <h2 className="text-2xl font-semibold flex items-center gap-2">
          <LayoutDashboard className="w-6 h-6 text-indigo-500" /> Dashboard Cards
        </h2>
        <button
          type="button"
          onClick={showAll}
          disabled={isLoading || hiddenCount === 0}
          className="px-3 py-1.5 text-sm rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Show all
        </button>
      </div>

      <p className={`text-sm mb-6 ${theme === "dark" ? "text-gray-400" : "text-gray-500"}`}>
        Choose which stat cards and charts appear on your Dashboard. Changes apply to your view of the Dashboard only.
      </p>

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="bg-red-600/90 text-white p-4 rounded-lg mb-4 shadow"
          >
            {error}
            <button onClick={() => setError(null)} className="ml-4 text-sm underline">
              Dismiss
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {isLoading ? (
        <div className="flex justify-center items-center h-40">
          <FaSpinner className="animate-spin text-3xl text-indigo-500" />
        </div>
      ) : available.length === 0 ? (
        <div className={`text-center py-10 ${theme === "dark" ? "text-gray-400" : "text-gray-500"}`}>
          <Eye className="w-8 h-8 mx-auto mb-2 opacity-50" />
          No dashboard items available.
        </div>
      ) : (
        <div className="space-y-6">
          {groups.map(({ groupName, items }) => (
            <section key={groupName}>
              <h3 className="text-lg font-semibold mb-3">{groupName}</h3>
              <div className={`rounded-lg divide-y ${
                theme === "dark" ? "bg-gray-700 divide-gray-600" : "bg-gray-100 divide-gray-200"
              }`}>
                {items.map((item) => {
                  const isVisible = !hidden.has(item.key);
                  return (
                    <div key={item.key} className="flex items-center justify-between p-4">
                      <div>
                        <p className="font-medium">{item.label}</p>
                        <p className={`text-xs mt-0.5 ${theme === "dark" ? "text-gray-400" : "text-gray-500"}`}>
                          {isVisible ? "Visible on Dashboard" : "Hidden from Dashboard"}
                        </p>
                      </div>
                      <Switch
                        checked={isVisible}
                        onChange={() => toggleItem(item.key)}
                        theme={theme}
                        label={`${isVisible ? "Hide" : "Show"} ${item.label} on Dashboard`}
                      />
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
};

export default DashboardCardPreferences;
