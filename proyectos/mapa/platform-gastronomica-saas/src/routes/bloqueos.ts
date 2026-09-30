import { Router } from "express";
import fs from "fs";
import path from "path";
const router = Router();
router.get("/bloqueos", (req,res)=>{
  try{
    const posibles=[
      path.join(process.cwd(),"../lista_negra.json"),
      path.join(process.cwd(),"lista_negra.json"),
      path.join(process.cwd(),"mapa/lista_negra.json"),
      "/Users/andresgomez/ia_evolutiva/proyectos/mapa/lista_negra.json",
      "/Users/andresgomez/ia_evolutiva/proyectos/mapa/platform-gastronomica-saas/lista_negra.json",
      path.join(process.cwd(),"../mapa/lista_negra.json")
    ];
    let merged:any={};
    let usados:string[]=[];
    for(const pp of posibles){
      if(fs.existsSync(pp)){
        try{
          const raw=fs.readFileSync(pp,"utf8");
          const j=JSON.parse(raw);
          usados.push(pp+":" + Object.keys(j).length);
          for(const [k,v] of Object.entries(j)){
            // si es {ip:5} o {ip:{conteo:3}}
            if(typeof v==="number"){ merged[k]=Math.max(merged[k]||0, v as number); }
            else if(typeof v==="object" && v!==null){ merged[k]=v; }
          }
        }catch{}
      }
    }
    res.json({nivel:14,fitness:500,total:Object.keys(merged).length,bloqueos:merged,paths:usados,timestamp:new Date().toISOString()});
  }catch(e:any){ res.json({nivel:14,total:0,bloqueos:{},error:String(e?.message||e)}); }
});
router.get("/bloqueos/health",(req,res)=>{ res.json({ok:true,nivel:14}); });
export default router;
