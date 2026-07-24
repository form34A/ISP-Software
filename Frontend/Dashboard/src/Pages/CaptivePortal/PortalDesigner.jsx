import React, { useMemo, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Wifi,
  Cable,
  Smartphone,
  Tablet,
  Monitor,
  RefreshCw,
  ExternalLink,
  AlertTriangle,
  ChevronDown,
  Paintbrush,
  FileText,
  LogIn,
  CreditCard,
  Clock,
  Globe,
  Settings as SettingsIcon,
} from "lucide-react";
import { useTheme } from "../../context/ThemeContext";
import { getThemeClasses } from "../../components/ServiceManagement/Shared/components";

const CONNECTION_TYPES = [
  { id: "hotspot", label: "Hotspot", icon: Wifi, path: "/hotspot" },
  { id: "pppoe", label: "PPPoE", icon: Cable, path: "/pppoe" },
];

const DEVICE_SIZES = [
  { id: "phone", label: "Phone", icon: Smartphone, width: "375px" },
  { id: "tablet", label: "Tablet", icon: Tablet, width: "768px" },
  { id: "desktop", label: "Desktop", icon: Monitor, width: "100%" },
];

const SETTINGS_SECTIONS = [
  {
    id: "branding",
    title: "Branding",
    icon: Paintbrush,
    description: "Logo, color palette, and background imagery shown to connecting subscribers.",
  },
  {
    id: "content",
    title: "Content",
    icon: FileText,
    description: "Headline copy, terms & conditions text, and support contact details.",
  },
  {
    id: "login-methods",
    title: "Login Methods",
    icon: LogIn,
    description: "Which authentication options (SMS, voucher, social login) are offered at sign-in.",
  },
  {
    id: "plans-payment",
    title: "Plans & Payment",
    icon: CreditCard,
    description: "Which service plans are displayed for purchase and how payment is collected.",
  },
  {
    id: "devices",
    title: "Devices",
    icon: Smartphone,
    description: "Per-device-type layout and behavior overrides for phones, tablets, and desktops.",
  },
  {
    id: "sessions",
    title: "Sessions",
    icon: Clock,
    description: "Session duration, idle timeouts, and re-authentication rules.",
  },
  {
    id: "language",
    title: "Language",
    icon: Globe,
    description: "Available languages and translated copy for the portal interface.",
  },
  {
    id: "advanced",
    title: "Advanced",
    icon: SettingsIcon,
    description: "Custom CSS/JS injection and other low-level overrides.",
  },
];

const PortalDesigner = () => {
  const { theme } = useTheme();
  const themeClasses = getThemeClasses(theme);

  const [connectionType, setConnectionType] = useState("hotspot");
  const [deviceSize, setDeviceSize] = useState("desktop");
  const [reloadNonce, setReloadNonce] = useState(0);
  const [openSection, setOpenSection] = useState(null);

  const iframeSrc = useMemo(() => {
    const basePath = CONNECTION_TYPES.find((t) => t.id === connectionType)?.path || "/hotspot";
    const params = new URLSearchParams({ connection_type: connectionType });
    if (reloadNonce > 0) params.set("_designer_reload", String(reloadNonce));
    return `${basePath}?${params.toString()}`;
  }, [connectionType, reloadNonce]);

  const activeDevice = DEVICE_SIZES.find((d) => d.id === deviceSize) || DEVICE_SIZES[2];

  const handleReload = useCallback(() => {
    setReloadNonce((n) => n + 1);
  }, []);

  const toggleSection = useCallback((id) => {
    setOpenSection((prev) => (prev === id ? null : id));
  }, []);

  return (
    <div className={`min-h-screen transition-colors duration-300 ${themeClasses.bg.primary}`}>
      <div className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto">
        {/* Header */}
        <header className="mb-8">
          <h1 className={`text-2xl md:text-3xl lg:text-4xl font-bold mb-2 ${themeClasses.text.primary}`}>
            Portal Designer
          </h1>
          <p className={`text-sm md:text-base ${themeClasses.text.secondary}`}>
            Preview the live captive portal and, in a future update, customize it from here.
          </p>
        </header>

        <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
          {/* Settings panel: preview comes first on small screens (order-2 here), side-by-side on large screens */}
          <div className="order-2 w-full space-y-4 lg:order-1 lg:w-2/5">
            <div className={`rounded-xl border p-4 ${themeClasses.bg.card} ${themeClasses.border.light}`}>
              <h2 className={`text-lg font-semibold mb-1 ${themeClasses.text.primary}`}>
                Settings
              </h2>
              <p className={`text-xs mb-4 ${themeClasses.text.tertiary}`}>
                Structure only — nothing below is wired up yet.
              </p>

              <div className="space-y-2">
                {SETTINGS_SECTIONS.map((section) => {
                  const Icon = section.icon;
                  const isOpen = openSection === section.id;

                  return (
                    <div
                      key={section.id}
                      className={`rounded-lg border opacity-60 ${themeClasses.border.light}`}
                    >
                      <button
                        type="button"
                        onClick={() => toggleSection(section.id)}
                        className={`w-full flex items-center justify-between gap-3 px-3 py-2.5 text-left cursor-not-allowed`}
                        aria-expanded={isOpen}
                      >
                        <span className="flex items-center gap-3 min-w-0">
                          <Icon className={`w-4 h-4 shrink-0 ${themeClasses.text.tertiary}`} />
                          <span className={`text-sm font-medium truncate ${themeClasses.text.primary}`}>
                            {section.title}
                          </span>
                        </span>
                        <span className="flex items-center gap-2 shrink-0">
                          <span
                            className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full ${themeClasses.bg.secondary} ${themeClasses.text.tertiary}`}
                          >
                            Not wired
                          </span>
                          <ChevronDown
                            className={`w-4 h-4 transition-transform ${themeClasses.text.tertiary} ${isOpen ? "rotate-180" : ""}`}
                          />
                        </span>
                      </button>

                      <AnimatePresence initial={false}>
                        {isOpen && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.15 }}
                            className="overflow-hidden"
                          >
                            <div className={`px-3 pb-3 text-xs ${themeClasses.text.secondary}`}>
                              {section.description}
                              <div
                                className={`mt-2 rounded border border-dashed px-3 py-2 ${themeClasses.border.medium} ${themeClasses.text.tertiary}`}
                              >
                                No controls yet — this section is a placeholder.
                              </div>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Preview pane */}
          <div className="order-1 w-full space-y-4 lg:order-2 lg:w-3/5">
            <div className={`rounded-xl border p-4 ${themeClasses.bg.card} ${themeClasses.border.light}`}>
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-4">
                {/* Connection type toggle */}
                <div className={`inline-flex rounded-lg border p-1 ${themeClasses.border.light}`}>
                  {CONNECTION_TYPES.map((type) => {
                    const Icon = type.icon;
                    const isActive = connectionType === type.id;
                    return (
                      <button
                        key={type.id}
                        type="button"
                        onClick={() => setConnectionType(type.id)}
                        className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                          isActive
                            ? themeClasses.button.primary
                            : `${themeClasses.text.secondary} hover:${theme === "dark" ? "bg-gray-700" : "bg-gray-100"}`
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                        {type.label}
                      </button>
                    );
                  })}
                </div>

                {/* Device size buttons */}
                <div className={`inline-flex rounded-lg border p-1 ${themeClasses.border.light}`}>
                  {DEVICE_SIZES.map((device) => {
                    const Icon = device.icon;
                    const isActive = deviceSize === device.id;
                    return (
                      <button
                        key={device.id}
                        type="button"
                        onClick={() => setDeviceSize(device.id)}
                        title={device.label}
                        aria-label={device.label}
                        className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                          isActive
                            ? themeClasses.button.primary
                            : `${themeClasses.text.secondary} hover:${theme === "dark" ? "bg-gray-700" : "bg-gray-100"}`
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                        <span className="hidden sm:inline">{device.label}</span>
                      </button>
                    );
                  })}
                </div>

                {/* Reload + open-in-new-tab */}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleReload}
                    title="Reload preview"
                    aria-label="Reload preview"
                    className={`p-2 rounded-lg ${themeClasses.button.secondary}`}
                  >
                    <RefreshCw className="w-4 h-4" />
                  </button>
                  <a
                    href={iframeSrc}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Open in new tab"
                    aria-label="Open in new tab"
                    className={`p-2 rounded-lg inline-flex ${themeClasses.button.secondary}`}
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              </div>

              {/* Live notice */}
              <div
                className={`flex items-start gap-3 mb-4 p-3 rounded-lg border ${themeClasses.bg.warning} ${themeClasses.border.warning}`}
              >
                <AlertTriangle className={`w-5 h-5 shrink-0 mt-0.5 ${themeClasses.text.warning}`} />
                <p className={`text-xs sm:text-sm ${themeClasses.text.warning}`}>
                  This is the current live captive portal, shown unmodified. Known defects in the
                  live portal are not fixed by this preview or by Portal Designer.
                </p>
              </div>

              {/* Iframe */}
              <div className="w-full flex justify-center">
                <div
                  className="transition-all duration-300 w-full"
                  style={{ maxWidth: activeDevice.width }}
                >
                  <div className={`rounded-lg border overflow-hidden ${themeClasses.border.medium}`}>
                    <iframe
                      key={iframeSrc}
                      src={iframeSrc}
                      title="Captive portal preview"
                      className="w-full bg-white"
                      style={{ height: "640px", border: "none" }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PortalDesigner;
