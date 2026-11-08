import { useCallback, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import {
  isTeacherLoggedIn,
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
import { TeacherLoginPage } from "./pages/teacher/TeacherLoginPage";
import { WaitingRoomPage } from "./pages/teacher/WaitingRoomPage";

export function isLoopbackHost(): boolean {
  if (typeof window === "undefined") return true;
  const h = window.location.hostname;
  return h === "localhost" || h === "127.0.0.1" || h === "[::1]" || h === "";
}

export function AppRoutes() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [network, setNetwork] = useState<NetworkStatusResponse | null>(null);
  const [networkError, setNetworkError] = useState<string | null>(null);
  const [selectedIp, setSelectedIp] = useState<string | undefined>(undefined);
  const [teacherAuthed, setTeacherAuthed] = useState<boolean>(() => isTeacherLoggedIn());

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

  const handleLoginSuccess = () => {
    setTeacherAuthed(true);
  };

  return (
    <Routes>
      {/* Student Entry Routes — Available to all LAN and Local clients */}
      <Route
        path="/join"
        element={<StudentJoinShell health={health} healthError={healthError} />}
      />
      <Route
        path="/student"
        element={<StudentJoinShell health={health} healthError={healthError} />}
      />

      {/* Explicit Teacher Login Route */}
      <Route
        path="/teacher/login"
        element={<TeacherLoginPage onLoginSuccess={handleLoginSuccess} />}
      />

      {/* When Teacher is authenticated: full Teacher Console */}
      {teacherAuthed ? (
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
                <Route
                  path="/dashboard"
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
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </TeacherLayout>
          }
        />
      ) : (
        /* When NOT authenticated:
           - LAN devices (phones) visiting root or any teacher path are redirected to /join.
           - Host PC (loopback) sees the Teacher PIN Login page.
        */
        <Route
          path="*"
          element={
            isLoopbackHost() ? (
              <TeacherLoginPage onLoginSuccess={handleLoginSuccess} />
            ) : (
              <Navigate to="/join" replace />
            )
          }
        />
      )}
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
