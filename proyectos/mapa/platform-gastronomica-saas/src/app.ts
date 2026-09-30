import express from "express";
import cors from "cors";
import chatRouter from "./routes/chat";
import bloqueosRouter from "./routes/bloqueos";

export const app = express();
app.use(cors());
app.use(express.json());
app.use(bloqueosRouter);
app.use("/api/chat", chatRouter);
app.get("/health", (req, res) => {
  res.json({ok:true, service:"gastronomica-saas", port:3001, restaurantes:"http://localhost:8001/restaurantes", platos:"http://localhost:8001/restaurantes/1/platos"});
});
