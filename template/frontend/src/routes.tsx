import { Link, Navigate, Outlet, createBrowserRouter, useLocation } from "react-router";
import { userManager } from "@/auth/userManager";
import { BrandMark } from "@/components/BrandMark";
import { MockPaymentBanner } from "@/components/MockPaymentBanner";
import { Billing } from "@/pages/Billing";
import { CheckoutReturn } from "@/pages/CheckoutReturn";
import { CreateWorkspace } from "@/pages/CreateWorkspace";
import { Home } from "@/pages/Home";
import { MockPayment } from "@/pages/MockPayment";
import { Plans } from "@/pages/Plans";
import { PremiumReport } from "@/pages/PremiumReport";

function Layout() {
  const { pathname } = useLocation();
  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <nav className="flex items-center gap-4 text-sm">
        <BrandMark className="mr-2 text-base" />
        <Link to="/premium">Report</Link>
        <Link to="/plans">Plans</Link>
        <Link to="/billing">Billing</Link>
        <button type="button" className="ml-auto" onClick={() => void userManager.signoutRedirect()}>Sign out</button>
      </nav>
      {/* Keyed so it asks again on every page: there is no workspace to ask about until one exists. */}
      <MockPaymentBanner key={pathname} />
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
      { path: "/billing/mock-payment", element: <MockPayment /> },
      { path: "/billing/return", element: <CheckoutReturn /> },
      { path: "/premium", element: <PremiumReport /> },
      { path: "/callback", element: <Navigate to="/" replace /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
