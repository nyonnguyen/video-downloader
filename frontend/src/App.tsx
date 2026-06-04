import { Navigate, Route, Routes } from "react-router-dom";
import { SideBar } from "@/components/SideBar";
import { Dashboard } from "@/routes/Dashboard";
import { Jobs } from "@/routes/Jobs";
import { Library } from "@/routes/Library";
import { Settings } from "@/routes/Settings";
import { useWebSocketBootstrap } from "@/lib/ws";

export default function App() {
  useWebSocketBootstrap();
  return (
    <div className="flex h-full">
      <SideBar />
      <main className="flex-1 overflow-y-auto p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/library" element={<Library />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/queue" element={<Navigate to="/jobs" replace />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/library" replace />} />
        </Routes>
      </main>
    </div>
  );
}
