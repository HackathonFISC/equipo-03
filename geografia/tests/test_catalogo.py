"""Integridad del catálogo de referencia y de sus alias; no validación en campo."""
import csv
import tempfile
import shutil
import unittest
from collections import Counter
from pathlib import Path

from geografia.generar_semilla import generar, leer_catalogo, normalizar

RAIZ=Path(__file__).resolve().parents[2]


class TestCatalogo(unittest.TestCase):
    def setUp(self):
        self.temporal=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.raiz=Path(self.temporal.name)
        shutil.copytree(RAIZ/'datos/geografia',self.raiz/'datos/geografia')
        (self.raiz/'supabase/seed').mkdir(parents=True)
        (self.raiz/'supabase/tests').mkdir(parents=True)

    def editar(self,archivo,mutar):
        ruta=self.raiz/'datos/geografia'/archivo
        with ruta.open(encoding='utf-8',newline='') as f:
            lector=csv.DictReader(f);campos=lector.fieldnames;filas=list(lector)
        mutar(filas)
        with ruta.open('w',encoding='utf-8',newline='') as f:
            escritor=csv.DictWriter(f,fieldnames=campos);escritor.writeheader();escritor.writerows(filas)

    def test_seis_puntos_tres_por_distrito_con_procedencia(self):
        filas=leer_catalogo(self.raiz)
        self.assertEqual(Counter(r['distrito'] for r in filas),{'Arraiján':3,'La Chorrera':3})
        self.assertTrue(all(r['fuente_periodo']=='2022-01' and r['fecha_consulta']=='2026-10-16' for r in filas))
        self.assertTrue({r['punto_atencion_id'] for r in filas}.isdisjoint({r['sector_id'] for r in filas}))

    def test_no_se_reutilizan_ids_de_fixtures_sinteticos(self):
        # Identidades de contratos V0: no convertir un punto sintético en lugar real.
        antiguos={'e42009e1-0718-57dd-bacf-6c0a8d6a8521','8e69dc43-1fdf-50ea-ba2f-0b28c7838e49',
                  '01b0918b-4d9d-5dc7-af69-b652621df104','9da59967-8d01-56df-b087-969033099193',
                  'f5cc6900-9694-5bb7-9dc9-13d568635dcf','1833d60c-30f3-5c23-9e0a-a2a0ad523c42'}
        self.assertTrue({r['punto_atencion_id'] for r in leer_catalogo(self.raiz)}.isdisjoint(antiguos))

    def test_rechaza_perder_balance_o_repetir_uuid(self):
        self.editar('puntos.csv',lambda f:f[0].update(distrito='La Chorrera'))
        with self.assertRaises(ValueError): leer_catalogo(self.raiz)

    def test_rechaza_coordenadas_no_finitas_o_inyectadas(self):
        for valor in ['NaN','Infinity','91','8.9); DELETE FROM public.reportes;']:
            self.editar('puntos.csv',lambda f:f[0].update(latitud=valor))
            with self.subTest(valor=valor),self.assertRaises(ValueError): leer_catalogo(self.raiz)

    def test_no_presentar_candidato_como_operativamente_validado(self):
        for campo,valor in [('estado_validacion','validada'),('representa_punto_atencion','true'),('capacidad_recepcion_litros','0')]:
            self.editar('puntos.csv',lambda f:f[0].update({campo:valor}))
            with self.subTest(campo=campo),self.assertRaises(ValueError): leer_catalogo(self.raiz)
            self.editar('puntos.csv',lambda f:f[0].update({campo:'pendiente' if campo=='estado_validacion' else ''}))

    def test_alias_amplio_o_sin_punto_no_pasa(self):
        self.editar('alias.csv',lambda f:f[0].update(alias='Vista Alegre'))
        with self.assertRaises(ValueError): generar(self.raiz)
        self.editar('alias.csv',lambda f:f[0].update(alias='Nombre específico',punto_atencion_id='00000000-0000-0000-0000-000000000000'))
        with self.assertRaises(ValueError): generar(self.raiz)

    def test_carga_en_un_bloque_atomico(self):
        sql=generar(self.raiz).read_text()
        self.assertEqual(sql.count('DO $catalogo$'),1)
        self.assertIn('DROP TABLE pg_temp.ra_catalogo_oeste;',sql)
        self.assertTrue(sql.rstrip().endswith('END $catalogo$;'))
        self.assertNotIn('COMMIT;',sql)

    def test_archivos_sql_versionados_coinciden_con_csv(self):
        generar(self.raiz)
        for nombre in ['supabase/seed/01_sectores_puntos.sql','supabase/tests/01_sectores_puntos_smoke.sql']:
            self.assertEqual((self.raiz/nombre).read_text(),(RAIZ/nombre).read_text())


if __name__=='__main__': unittest.main()
