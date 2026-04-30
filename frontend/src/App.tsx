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
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
