import express, { type Express } from "express";
import cors from "cors";
import pinoHttp from "pino-http";
import fs from "node:fs";
import path from "node:path";
import router from "./routes";
import { logger } from "./lib/logger";

const app: Express = express();

app.use(
  pinoHttp({
    logger,
    serializers: {
      req(req) {
        return {
          id: req.id,
          method: req.method,
          url: req.url?.split("?")[0],
        };
      },
      res(res) {
        return {
          statusCode: res.statusCode,
        };
      },
    },
  }),
);
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.use("/api", router);

// In production Railway runs the frontend and API in one service. During
// local development the frontend still runs in its own Vite workflow, so
// static serving is enabled only when the built frontend exists.
const frontendDistDir =
  process.env.FRONTEND_DIST_DIR ??
  path.resolve(import.meta.dirname, "../../ad-intel/dist/public");
const frontendIndex = path.join(frontendDistDir, "index.html");

if (fs.existsSync(frontendIndex)) {
  app.use(express.static(frontendDistDir));
  app.use((req, res, next) => {
    if (req.method !== "GET" || req.path.startsWith("/api")) {
      next();
      return;
    }
    res.sendFile(frontendIndex);
  });
}

export default app;
