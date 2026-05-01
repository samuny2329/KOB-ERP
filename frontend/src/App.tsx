import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "@/components/Layout";
import LoginPage from "@/pages/LoginPage";
import HomePage from "@/pages/HomePage";
import PreviewHomePage from "@/pages/PreviewHomePage";
import ProductsPage from "@/pages/ProductsPage";
import WarehousesPage from "@/pages/WarehousesPage";
import TransfersPage from "@/pages/TransfersPage";
import OutboundPage from "@/pages/OutboundPage";
import CouriersPage from "@/pages/CouriersPage";
import CountsPage from "@/pages/CountsPage";
import QualityPage from "@/pages/QualityPage";
import ActivityLogPage from "@/pages/ActivityLogPage";
import OpsPage from "@/pages/OpsPage";
import PurchasePage from "@/pages/PurchasePage";
import ManufacturingPage from "@/pages/ManufacturingPage";
import SalesPage from "@/pages/SalesPage";
import AccountingPage from "@/pages/AccountingPage";
import HRPage from "@/pages/HRPage";
import UsersPage from "@/pages/UsersPage";
import GroupHubPage from "@/pages/group/GroupHubPage";
import CrossCompanyCustomersPage from "@/pages/group/CrossCompanyCustomersPage";
import CrossCompanyVendorsPage from "@/pages/group/CrossCompanyVendorsPage";
import TreasuryPage from "@/pages/group/TreasuryPage";
import CompliancePage from "@/pages/group/CompliancePage";
import ApprovalsPage from "@/pages/group/ApprovalsPage";
import { useAuth } from "@/lib/auth";

function ProtectedRoute({ children }: { children: React.ReactElement }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-slate-500">Loading…</div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/preview-launcher" element={<PreviewHomePage />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<HomePage />} />
        <Route path="/products" element={<ProductsPage />} />
        <Route path="/warehouses" element={<WarehousesPage />} />
        <Route path="/transfers" element={<TransfersPage />} />
        <Route path="/outbound" element={<OutboundPage />} />
        <Route path="/couriers" element={<CouriersPage />} />
        <Route path="/counts" element={<CountsPage />} />
        <Route path="/quality" element={<QualityPage />} />
        <Route path="/audit" element={<ActivityLogPage />} />
        <Route path="/ops" element={<OpsPage />} />
        <Route path="/purchase" element={<PurchasePage />} />
        <Route path="/manufacturing" element={<ManufacturingPage />} />
        <Route path="/sales" element={<SalesPage />} />
        <Route path="/accounting" element={<AccountingPage />} />
        <Route path="/hr" element={<HRPage />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="/group" element={<GroupHubPage />} />
        <Route path="/group/customers" element={<CrossCompanyCustomersPage />} />
        <Route path="/group/vendors" element={<CrossCompanyVendorsPage />} />
        <Route path="/group/treasury" element={<TreasuryPage />} />
        <Route path="/group/compliance" element={<CompliancePage />} />
        <Route path="/group/approvals" element={<ApprovalsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
