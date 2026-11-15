import { lazy, Suspense, type ReactNode } from 'react';
import { Route, Routes } from 'react-router-dom';
import RequireAuth from './auth/RequireAuth';
import AppShell from './layout/AppShell';
import ChangePasswordPage from './pages/ChangePasswordPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import HomePage from './pages/HomePage';
import NotFoundPage from './pages/NotFoundPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import SignInPage from './pages/SignInPage';

// Pages beyond sign-in load on demand, so field offices on slow links download only what they open
// (the charting library in particular).
const AuditPage = lazy(() => import('./pages/AuditPage'));
const GroupsPage = lazy(() => import('./pages/GroupsPage'));
const SecurityPage = lazy(() => import('./pages/SecurityPage'));
const SetupWizardPage = lazy(() => import('./pages/SetupWizardPage'));
const StructurePage = lazy(() => import('./pages/structure/StructurePage'));
const UsersPage = lazy(() => import('./pages/UsersPage'));
const FiscalYearsPage = lazy(() => import('./pages/planning/FiscalYearsPage'));
const ScoringProfilePage = lazy(() => import('./pages/planning/ScoringProfilePage'));
const FiscalYearPage = lazy(() => import('./pages/planning/FiscalYearPage'));
const PlansPage = lazy(() => import('./pages/planning/PlansPage'));
const PlanEditorPage = lazy(() => import('./pages/planning/PlanEditorPage'));
const PlanVersionsPage = lazy(() => import('./pages/planning/PlanVersionsPage'));
const ApprovalsPage = lazy(() => import('./pages/planning/ApprovalsPage'));
const MonthlyReportPage = lazy(() => import('./pages/reporting/MonthlyReportPage'));
const DashboardPage = lazy(() => import('./pages/dashboard/DashboardPage'));
const RankingsPage = lazy(() => import('./pages/dashboard/RankingsPage'));
const SubmissionBoardPage = lazy(() => import('./pages/reporting/SubmissionBoardPage'));
const MyExportsPage = lazy(() => import('./pages/exports/MyExportsPage'));
const PlatformAgenciesPage = lazy(() => import('./platform/PlatformAgenciesPage'));
const PlatformSignInPage = lazy(() => import('./platform/PlatformSignInPage'));

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
          path="account/security"
          element={
            <Page>
              <SecurityPage />
            </Page>
          }
        />
        <Route
          path="structure"
          element={
            <Page>
              <StructurePage />
            </Page>
          }
        />
        <Route
          path="groups"
          element={
            <Page>
              <GroupsPage />
            </Page>
          }
        />
        <Route
          path="users"
          element={
            <Page>
              <UsersPage />
            </Page>
          }
        />
        <Route
          path="setup"
          element={
            <Page>
              <SetupWizardPage />
            </Page>
          }
        />
        <Route
          path="audit"
          element={
            <Page>
              <AuditPage />
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
              <FiscalYearPage />
            </Page>
          }
        />
        <Route
          path="fiscal-years/:fyId/scoring"
          element={
            <Page>
              <ScoringProfilePage />
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
              <PlanEditorPage />
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
          path="submissions"
          element={
            <Page>
              <SubmissionBoardPage />
            </Page>
          }
        />
        <Route
          path="reports"
          element={
            <Page>
              <MonthlyReportPage />
            </Page>
          }
        />
        <Route
          path="plans/approvals"
          element={
            <Page>
              <ApprovalsPage />
            </Page>
          }
        />
        <Route
          path="plans/:planId/versions"
          element={
            <Page>
              <PlanVersionsPage />
            </Page>
          }
        />
      </Route>
      <Route
        path="/platform/sign-in"
        element={
          <Page>
            <PlatformSignInPage />
          </Page>
        }
      />
      <Route
        path="/platform"
        element={
          <Page>
            <PlatformAgenciesPage />
          </Page>
        }
      />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
