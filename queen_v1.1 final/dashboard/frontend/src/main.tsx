import React from "react";
import ReactDOM from "react-dom/client";
import { MantineProvider, createTheme } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { EventsProvider } from "./ws/useEvents";
import App from "./App";

import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";

const theme = createTheme({
  primaryColor: "violet",
  defaultRadius: "md",
  fontFamily: "Inter, system-ui, -apple-system, sans-serif",
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <MantineProvider theme={theme} defaultColorScheme="dark">
        <Notifications position="top-right" />
        <EventsProvider>
          <App />
        </EventsProvider>
      </MantineProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
