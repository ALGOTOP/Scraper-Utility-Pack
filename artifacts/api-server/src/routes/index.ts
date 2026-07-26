import { Router, type IRouter } from "express";
import healthRouter from "./health.js";
import jobsRouter from "./jobs.js";
import leadsRouter from "./leads.js";
import savedSearchesRouter from "./saved-searches.js";
import dashboardRouter from "./dashboard.js";

const router: IRouter = Router();

router.use(healthRouter);
router.use(jobsRouter);
router.use(leadsRouter);
router.use(savedSearchesRouter);
router.use(dashboardRouter);

export default router;
