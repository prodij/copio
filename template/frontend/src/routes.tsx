import { Link, Navigate, Outlet, createBrowserRouter } from "react-router";
import { Billing } from "@/pages/Billing";
import { CheckoutReturn } from "@/pages/CheckoutReturn";
import { CreateWorkspace } from "@/pages/CreateWorkspace";
import { Home } from "@/pages/Home";
import { Plans } from "@/pages/Plans";
import { PremiumReport } from "@/pages/PremiumReport";

function Layout() {
  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <nav className="flex gap-4 text-sm">
        <Link to="/premium">Report</Link>
        <Link to="/plans">Plans</Link>
        <Link to="/billing">Billing</Link>
      </nav>
      <Outlet />
    </div>
  );
}

export const routes = [
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/workspace/new", element: <CreateWorkspace /> },
      { path: "/plans", element: <Plans /> },
      { path: "/billing", element: <Billing /> },
      { path: "/billing/return", element: <CheckoutReturn /> },
      { path: "/premium", element: <PremiumReport /> },
      { path: "/callback", element: <Navigate to="/" replace /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
