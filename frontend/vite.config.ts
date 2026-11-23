import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { fileURLToPath, URL } from "node:url";

const STATIC = process.env.VITE_STATIC === "1";

export default defineConfig({
  plugins: [
    react(),
    !STATIC && VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg", "apple-touch-icon.png"],
      manifest: {
        name: "iBBIBBI Insight Hub",
        short_name: "Insight Hub",
        description: "Customer feedback, social and sales insights for the iBBIBBI founders.",
        theme_color: "#2E5E5A",
        background_color: "#FBF8F4",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api/],
        runtimeCaching: [{ urlPattern: /\/api\/.*/, handler: "NetworkFirst", options: { cacheName: "api", networkTimeoutSeconds: 4 } }],
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
      },
    }),
  ],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" }, fs: { allow: [".."] } },
  build: STATIC
    ? { outDir: "dist-prototype", assetsInlineLimit: 100_000_000, cssCodeSplit: false, chunkSizeWarningLimit: 5000, rollupOptions: { output: { inlineDynamicImports: true } } }
    : { chunkSizeWarningLimit: 1500 },
});
