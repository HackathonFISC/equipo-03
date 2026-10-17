// Integración aislada. PGlite es una herramienta temporal; no conecta a servicios.
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const require=createRequire(process.env.RA_PGLITE_PACKAGE ? path.resolve(process.env.RA_PGLITE_PACKAGE) : import.meta.url);
const {PGlite}=await import(pathToFileURL(path.join(path.dirname(require.resolve('@electric-sql/pglite')),'index.js')).href);
import fs from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
const raiz=process.env.RA_REPO || fileURLToPath(new URL('../../',import.meta.url));
const python=process.env.RA_PYTHON || path.join(raiz,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
function py(obj){const r=spawnSync(python,['-m','agentes.tests.soporte_puente_necesidades'],{cwd:raiz,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},input:JSON.stringify(obj),encoding:'utf8',maxBuffer:10*1024*1024});if(r.status!==0)throw Error('Python: '+r.stderr);return JSON.parse(r.stdout);}
function comprobar(c,m){if(!c)throw Error(m);}
const db=new PGlite();
async function sql(t,p=[]){return (await db.query(t,p)).rows;}
async function rpc(n,p={}){const keys=Object.keys(p);return (await sql(`SELECT public.${n}(${keys.map((k,i)=>k+'=> $'+(i+1)).join(',')}) AS dato`,Object.values(p)))[0].dato;}
try {
 await db.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role BYPASSRLS; CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY);');
 const migraciones=['0001_esquema.sql','0004_identidad_reportes.sql','0005_ingesta_transaccional.sql','0006_aclaraciones_v2.sql','0007_territorial_orquestador_v2.sql','0008_idempotencia_lotes.sql','0009_planificacion_v3.sql','0010_ensayos_priorizacion_v2.sql','0011_bandeja_salida.sql','0003_aprobacion.sql','0012_comunicacion_v4.sql','0013_feedback_aclaraciones.sql','0014_recuperacion_trabajador.sql','0015_ingesta_recuperable.sql','0016_puente_necesidades_v3.sql'];
 for(const m of migraciones)await db.exec(await fs.readFile(raiz+'/supabase/migrations/'+m,'utf8'));
 await db.exec(await fs.readFile(raiz+'/supabase/seed/01_sectores_puntos.sql','utf8'));
 const uid=(await sql('SELECT gen_random_uuid() AS id'))[0].id;
 await sql('INSERT INTO auth.users(id) VALUES($1)',[uid]);
 await sql("INSERT INTO public.usuarios_operativos(usuario_id,rol,activo,motivo) VALUES($1,'coordinador',true,'FIXTURE LOCAL A1')",[uid]);
 const {paquete,infraestructura:infra}=py({accion:'fixture',usuario_id:uid});
 const eid=paquete.ejecucion_id;const pol=paquete.lote.politica;
 await sql(`INSERT INTO public.politicas_prioridad(politica_version,estado,origen,peso_duracion,peso_vulnerabilidad,peso_poblacion,tope_horas,tope_personas,vulnerabilidad_moderada,fundamento,confirmacion_activacion)
 VALUES($1,'activa','sintetico',$2,$3,$4,$5,$6,$7,$8,$9)`,[pol.politica_version,pol.peso_duracion,pol.peso_vulnerabilidad,pol.peso_poblacion,pol.tope_horas,pol.tope_personas,pol.vulnerabilidad_moderada,pol.fundamento,pol.confirmacion_activacion]);
 let primero=true;
 for(const entrada of paquete.lote.entradas){
  const n=entrada.evaluacion;const punto=infra.puntos.find(p=>p.punto_atencion_id===n.punto_atencion_id);
  const ids=(await sql('SELECT gen_random_uuid() AS r,gen_random_uuid() AS u,gen_random_uuid() AS e'))[0];
  const actual=primero?eid:ids.e;primero=false;
  const texto=`En ${punto.nombre} llevamos ${n.horas_sin_agua} horas sin agua. Somos ${n.personas_atendidas} personas.`;
  await sql("INSERT INTO public.remitentes(remitente_ref,canal,identificador_externo) VALUES($1,'telegram',$2)",[ids.u,'fixture:'+ids.u]);
  await sql("INSERT INTO public.reportes(reporte_id,remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen) VALUES($1,$2,'telegram',$3,'texto',$4,'real')",[ids.r,ids.u,'fixture:'+ids.r,texto]);
  await sql("INSERT INTO public.ejecuciones(ejecucion_id,reporte_id,origen) VALUES($1,$2,'real')",[actual,ids.r]);
  let t=await rpc('ra_tomar_ingesta',{p_ejecucion_id:actual,p_trabajador_id:'fixture-a1'});
  const ingesta=py({accion:'ingesta',toma:t,nombre:punto.nombre,horas:n.horas_sin_agua,personas:n.personas_atendidas});
  await rpc('ra_finalizar_ingesta',{p_ejecucion_id:actual,p_trabajador_id:'fixture-a1',p_reporte_snapshot:t.reporte,p_resultado:ingesta.resultado,p_evento:ingesta.evento,p_error:null});
  t=await rpc('ra_tomar_etapa_v2',{p_ejecucion_id:actual,p_trabajador_id:'fixture-a1',p_etapa:'territorial'});
  const resolucion=py({accion:'territorial',toma:t});comprobar(resolucion.estado==='resuelta','Territorial no resolvió fixture');
  await rpc('ra_finalizar_territorial',{p_ejecucion_id:actual,p_trabajador_id:'fixture-a1',p_snapshot:t,p_resolucion:resolucion});
 }
 const incidentes=await rpc('ra_incidentes_contexto_v2',{p_ejecucion_id:eid});
 comprobar(incidentes.length===6,'Ámbito incompleto');
 for(const entrada of paquete.lote.entradas){
  const i=incidentes.find(i=>i.punto_atencion_id===entrada.solicitud_demanda.punto_atencion_id);
  entrada.version_incidente=i.version;
  for(const objeto of [entrada.solicitud_demanda,entrada.evaluacion])Object.assign(objeto,{ejecucion_id:eid,incidente_id:i.incidente_id,origen:'real'});
  entrada.evaluacion.primera_deteccion_en=i.primera_deteccion_en;
 }
 await rpc('ra_preparar_priorizacion_v2',{p_ejecucion_id:eid,p_usuario_id:uid,p_lote:paquete.lote});
 let toma=await rpc('ra_tomar_etapa_v2',{p_ejecucion_id:eid,p_trabajador_id:'fixture-a1',p_etapa:'priorizacion'});
 const priorizacion=py({accion:'priorizacion',toma});
 await rpc('ra_finalizar_priorizacion_v2',{p_ejecucion_id:eid,p_trabajador_id:'fixture-a1',p_snapshot:toma,p_resultado:priorizacion.resultado,p_pendientes:[],p_validaciones:priorizacion.validaciones});
 comprobar((await rpc('ra_puentes_pendientes_v3')).some(e=>e.ejecucion_id===eid),'Cola no persistida');
 const snapshot=await rpc('ra_contexto_puente_v3',{p_ejecucion_id:eid,p_infraestructura:infra});
 const solicitud=py({accion:'puente',snapshot});
 comprobar(solicitud.origen==='sintetico'&&solicitud.necesidades.every(n=>n.origen==='real'),'Se perdió procedencia o etiqueta');
 const reg=await rpc('ra_registrar_puente_v3',{p_ejecucion_id:eid,p_snapshot:snapshot,p_solicitud:solicitud});
 comprobar(reg.ejecucion_id===eid&&reg.etapa==='planificacion','No conservó ejecución');
 const repetido=await rpc('ra_registrar_puente_v3',{p_ejecucion_id:eid,p_snapshot:snapshot,p_solicitud:solicitud});
 comprobar(repetido.repetido===true,'Puente no idempotente');
 toma=await rpc('ra_tomar_planificacion_v3',{p_ejecucion_id:eid,p_trabajador_id:'fixture-a1'});
 const plan=py({accion:'planificacion',solicitud:toma.solicitud});
 comprobar(plan.estado==='espera_validacion'&&plan.informe.valido,'Solver/verificador rechazaron escenario');
 const cierre=await rpc('ra_finalizar_planificacion_v3',{p_ejecucion_id:eid,p_trabajador_id:'fixture-a1',p_snapshot:toma,p_resultado:plan});
 const pl=plan.propuesta;
 await rpc('ra_aprobar_plan',{p_usuario_id:uid,p_plan_id:pl.plan_id,p_version:1,p_datos_version:pl.datos_version,p_politica_version:pl.politica_version,p_motivo:'FIXTURE: aprobación humana simulada del ensayo',p_bloqueos_reconocidos:pl.bloqueos_publicacion});
 for(const sector of new Set(infra.puntos.map(p=>p.sector_id)))await rpc('ra_seleccionar_plan_sector_v4',{p_usuario_id:uid,p_sector_id:sector,p_plan_id:pl.plan_id,p_version:1,p_motivo:'FIXTURE: selección de ensayo'});
 const destino=(await sql("INSERT INTO public.destinos(canal,identificador_externo,autorizado,autorizado_por,autorizado_en,motivo) VALUES('telegram',$1,true,$2,now(),'FIXTURE: destino de ensayo') RETURNING destino_id",['fixture-chat:'+uid,uid]))[0].destino_id;
 for(const sector of new Set(infra.puntos.map(p=>p.sector_id)))await sql('INSERT INTO public.suscripciones_sector(destino_id,sector_id,activa) VALUES($1,$2,true)',[destino,sector]);
 let comunicacion=await rpc('ra_comunicar_plan_v4',{p_ejecucion_id:eid,p_trabajador_id:'fixture-a1'});
 comprobar(comunicacion.codigo==='destino_autorizado_pendiente','Un plan de ensayo escapó del destino habilitado');
 comprobar((await sql('SELECT count(*)::int AS n FROM public.avisos WHERE ejecucion_id=$1',[eid]))[0].n===0,'Se creó bandeja no autorizada');
 await rpc('ra_configurar_destino_ensayo_v4',{p_usuario_id:uid,p_destino_id:destino,p_habilitado:true,p_motivo:'FIXTURE: habilitar solo chat de prueba'});
 comunicacion=await rpc('ra_comunicar_plan_v4',{p_ejecucion_id:eid,p_trabajador_id:'fixture-a1'});
 const avisos=await sql('SELECT origen,estado_envio,texto FROM public.avisos WHERE ejecucion_id=$1',[eid]);
 comprobar(avisos.length===6&&avisos.every(a=>a.origen==='sintetico'&&a.estado_envio==='pendiente'&&a.texto.includes('No es una entrega real')),'Bandeja incorrecta');
 const agentes=(await sql('SELECT DISTINCT agente FROM public.eventos WHERE ejecucion_id=$1 AND agente IS NOT NULL ORDER BY agente',[eid])).map(x=>x.agente);
 comprobar(agentes.length===5,'Falta traza de los cinco agentes');
 comprobar((await sql('SELECT origen FROM public.ejecuciones WHERE ejecucion_id=$1',[eid]))[0].origen==='real','Se reetiquetó la ejecución');
 await sql("UPDATE public.necesidades SET motivo='FIXTURE: cambio después de aprobación' WHERE ejecucion_id=$1",[eid]);
 comprobar((await sql('SELECT estado FROM public.planes WHERE ejecucion_id=$1',[eid]))[0].estado==='invalidado','Cambio de necesidades no invalidó plan');
 comprobar((await sql("SELECT count(*)::int AS n FROM public.avisos WHERE ejecucion_id=$1 AND estado_envio='cancelado'",[eid]))[0].n===6,'Avisos no se cancelaron por cambio de entradas');
 const evidencia={fecha:new Date().toISOString(),modo:'integracion_local_controlada',datos_reales_usados:false,origen_probado:'real',origen_escenario:'sintetico',modo_plan:'ensayo',mismo_ejecucion_id:true,necesidades:6,litros_asignados:pl.rutas.flatMap(r=>r.paradas).reduce((a,p)=>a+p.litros_asignados,0),verificacion_valida:plan.informe.valido,agentes,traza_cinco_agentes:true,avisos_creados:avisos.length,telegram_real:false,gemini_real:false,aprobacion_humana:'simulada en fixture',destino_no_habilitado_bloqueado:true,plan_invalidado_tras_cambio_necesidades:true,avisos_cancelados_tras_cambio:6};
 await fs.writeFile(process.env.RA_EVIDENCIA || raiz+'/agentes/evidencias/puente_necesidades_v3_local.json',JSON.stringify(evidencia,null,2)+'\n');
 console.log(JSON.stringify(evidencia));
} catch(e){console.log('FALLO INTEGRACION:',e.message,e.code||'',e.where||'');process.exitCode=1;}
await db.close();
