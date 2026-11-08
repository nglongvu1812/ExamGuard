import { useCallback, useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import {
  systemApi,
  type HealthResponse,
  type NetworkStatusResponse,
} from "./api/client";
import { TeacherLayout } from "./layouts/TeacherLayout";
import { StudentJoinShell } from "./pages/student/StudentJoinShell";
import { ClassesPage } from "./pages/teacher/ClassesPage";
import { DashboardPage } from "./pages/teacher/DashboardPage";
import { LanHelpPage } from "./pages/teacher/LanHelpPage";
import { PaperBridgePage } from "./pages/teacher/PaperBridgePage";
import { QuestionBankPage } from "./pages/teacher/QuestionBankPage";
import { ResultsAuditPage } from "./pages/teacher/ResultsAuditPage";
import { SettingsBackupPage } from "./pages/teacher/SettingsBackupPage";
import { WaitingRoomPage } from "./pages/teacher/WaitingRoomPage";

export function AppRoutes() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [network, setNetwork] = useState<NetworkStatusResponse | null>(null);
  const [networkError, setNetworkError] = useState<string | null>(null);
  const [selectedIp, setSelectedIp] = useState<string | undefined>(undefined);

  const loadSystemState = useCallback(async (ip?: string) => {
    try {
      const h = await systemApi.getHealth();
      setHealth(h);
      setHealthError(null);
    } catch (err) {
      setHealth(null);
      setHealthError(err instanceof Error ? err.message : "Không thể kết nối máy chủ");
    }

    try {
      const n = await systemApi.getNetworkStatus(ip);
      setNetwork(n);
      setNetworkError(null);
    } catch (err) {
      setNetwork(null);
      setNetworkError(err instanceof Error ? err.message : "Không thể kiểm tra mạng LAN");
    }
  }, []);

  useEffect(() => {
    void loadSystemState(selectedIp);
  }, [loadSystemState, selectedIp]);

  const handleSelectIp = (ip: string) => {
    setSelectedIp(ip || undefined);
  };

  return (
    <Routes>
      <Route
        path="/join"
        element={<StudentJoinShell health={health} healthError={healthError} />}
      />
      <Route
        path="/student"
        element={<StudentJoinShell health={health} healthError={healthError} />}
      />
      <Route
        path="*"
        element={
          <TeacherLayout health={health} healthError={healthError}>
            <Routes>
              <Route
                path="/"
                element={
                  <DashboardPage
                    health={health}
                    network={network}
                    networkError={networkError}
                    onSelectIp={handleSelectIp}
                    onRefresh={() => void loadSystemState(selectedIp)}
                  />
                }
              />
              <Route path="/classes" element={<ClassesPage />} />
              <Route path="/questions" element={<QuestionBankPage />} />
              <Route path="/exams/new" element={<WaitingRoomPage />} />
              <Route path="/exams/:examId/waiting" element={<WaitingRoomPage />} />
              <Route path="/paper" element={<PaperBridgePage />} />
              <Route path="/results" element={<ResultsAuditPage />} />
              <Route
                path="/settings"
                element={<SettingsBackupPage health={health} />}
              />
              <Route
                path="/lan-help"
                element={<LanHelpPage network={network} onSelectIp={handleSelectIp} />}
              />
            </Routes>
          </TeacherLayout>
        }
      />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
