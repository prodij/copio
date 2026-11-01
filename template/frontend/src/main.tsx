import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { setTokenProvider } from "@/api/client";
import { accessToken } from "@/auth/userManager";
import { App } from "./App";
import "./index.css";

setTokenProvider(accessToken);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
