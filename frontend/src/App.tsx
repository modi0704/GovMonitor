import { lazy, Suspense, type ReactNode } from 'react';
import { Route, Routes, useParams } from 'react-router-dom';
import RequireAuth from './auth/RequireAuth';
import DesktopOnly from './components/DesktopOnly';
import AppShell from './layout/AppShell';
import ChangePasswordPage from './pages/ChangePasswordPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import HomePage from './pages/HomePage';
import NotFoundPage from './pages/NotFoundPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import SignInPage from './pages/SignInPage';

// Pages beyond sign-in load on demand, so field offices on slow links download only what they open
// (the charting library in particular).
const SetupWizardPage = lazy(() => import('./pages/SetupWizardPage'));
const StructurePage = lazy(() => import('./pages/structure/StructurePage'));
const FiscalYearsPage = lazy(() => import('./pages/planning/FiscalYearsPage'));
const FiscalYearPage = lazy(() => import('./pages/planning/FiscalYearPage'));
const PlansPage = lazy(() => import('./pages/planning/PlansPage'));
const PlanEditorPage = lazy(() => import('./pages/planning/PlanEditorPage'));
const MonthlyReportPage = lazy(() => import('./pages/reporting/MonthlyReportPage'));
const DashboardPage = lazy(() => import('./pages/dashboard/DashboardPage'));
const RankingsPage = lazy(() => import('./pages/dashboard/RankingsPage'));
const UserGuidePage = lazy(() => import('./pages/help/UserGuidePage'));
const MyExportsPage = lazy(() => import('./pages/exports/MyExportsPage'));

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Only a real plan id opens the editor: old addresses such as /plans/approvals are Not found. */
function PlanRoute({ children }: { children: ReactNode }) {
  const { planId } = useParams();
  return UUID.test(planId ?? '') ? <>{children}</> : <NotFoundPage />;
}

function Page({ children }: { children: ReactNode }) {
  return <Suspense fallback={<div className="page-loading">Loading…</div>}>{children}</Suspense>;
}

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
        <Route
          path="structure"
          element={
            <Page>
              <DesktopOnly what="The office structure">
                <StructurePage />
              </DesktopOnly>
            </Page>
          }
        />
        <Route
          path="setup"
          element={
            <Page>
              <DesktopOnly what="The setup wizard">
                <SetupWizardPage />
              </DesktopOnly>
            </Page>
          }
        />
        <Route
          path="fiscal-years"
          element={
            <Page>
              <FiscalYearsPage />
            </Page>
          }
        />
        <Route
          path="fiscal-years/:fyId"
          element={
            <Page>
              <DesktopOnly what="The fiscal year calendar">
                <FiscalYearPage />
              </DesktopOnly>
            </Page>
          }
        />
        <Route
          path="plans"
          element={
            <Page>
              <PlansPage />
            </Page>
          }
        />
        <Route
          path="plans/:planId"
          element={
            <Page>
              <PlanRoute>
                <DesktopOnly what="The plan editor">
                  <PlanEditorPage />
                </DesktopOnly>
              </PlanRoute>
            </Page>
          }
        />
        <Route
          path="user-guide"
          element={
            <Page>
              <UserGuidePage />
            </Page>
          }
        />
        <Route
          path="exports"
          element={
            <Page>
              <MyExportsPage />
            </Page>
          }
        />
        <Route
          path="rankings"
          element={
            <Page>
              <RankingsPage />
            </Page>
          }
        />
        <Route
          path="dashboard"
          element={
            <Page>
              <DashboardPage />
            </Page>
          }
        />
        <Route
          path="reports"
          element={
            <Page>
              <DesktopOnly what="The monthly report grid">
                <MonthlyReportPage />
              </DesktopOnly>
            </Page>
          }
        />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
