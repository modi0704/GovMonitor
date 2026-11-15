import { Route, Routes } from 'react-router-dom';
import RequireAuth from './auth/RequireAuth';
import AppShell from './layout/AppShell';
import ChangePasswordPage from './pages/ChangePasswordPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import HomePage from './pages/HomePage';
import NotFoundPage from './pages/NotFoundPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import SecurityPage from './pages/SecurityPage';
import SignInPage from './pages/SignInPage';
import StructurePage from './pages/structure/StructurePage';
import PlatformAgenciesPage from './platform/PlatformAgenciesPage';
import PlatformSignInPage from './platform/PlatformSignInPage';

export default function App() {
  return (
    <Routes>
      <Route path="/sign-in" element={<SignInPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route
        path="/change-password"
        element={
          <RequireAuth>
            <ChangePasswordPage />
          </RequireAuth>
        }
      />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="account/security" element={<SecurityPage />} />
        <Route path="structure" element={<StructurePage />} />
      </Route>
      <Route path="/platform/sign-in" element={<PlatformSignInPage />} />
      <Route path="/platform" element={<PlatformAgenciesPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
