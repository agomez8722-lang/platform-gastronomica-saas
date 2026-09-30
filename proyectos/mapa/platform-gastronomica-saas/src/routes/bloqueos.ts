import { Router } from "express";
import fs from "fs";
import path from "path";
const router = Router();
router.get("/bloqueos", (req,res)=>{
  try {
    const p = path.join(__dirname, "../../lista_negra.json");
    const data = JSON.parse(fs.readFileSync(p,"utf8"));
    res.json({nivel:14, fitness:500, total:Object.keys(data).length, bloqueos:data, timestamp:new Date().toISOString()});
  } catch(e){ res.json({nivel:14, total:0, bloqueos:{}, error:String(e)}); }
});
router.get("/bloqueos/health", (req,res)=>{ res.json({ok:true, nivel:14}); });
export default router;
