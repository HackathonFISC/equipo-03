"""Cotejo textual y unidades explícitas; no interpreta ni completa hechos."""
import re
import unicodedata


def normalizar(texto):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD',texto.casefold())
                            if not unicodedata.combining(c)).split())


def fragmento_original(fragmento, fuentes):
    """Devuelve una cita de UNA fuente; tolera solo caso, acentos y espacios."""
    buscado = normalizar(fragmento)
    if not buscado:
        return None
    for fuente in fuentes:
        letras, posiciones = [], []
        for indice, caracter in enumerate(fuente):
            piezas = ''.join(c for c in unicodedata.normalize('NFD',caracter.casefold())
                             if not unicodedata.combining(c))
            if not piezas and posiciones:
                posiciones[-1] = (posiciones[-1][0], indice+1)
            for c in piezas:
                if c.isspace():
                    if not letras:
                        continue
                    if letras[-1]==' ':
                        posiciones[-1]=(posiciones[-1][0],indice+1)
                        continue
                    c=' '
                letras.append(c); posiciones.append((indice,indice+1))
        inicio = ''.join(letras).find(buscado)
        if inicio>=0:
            return fuente[posiciones[inicio][0]:posiciones[inicio+len(buscado)-1][1]]
    return None


def cantidades_explicitas(fuentes):
    horas, personas = [], []
    for fuente in fuentes:
        texto = normalizar(fuente)
        for numero, unidad in re.findall(
                r'(?<![\w.,+\-])(\d+(?:[.,]\d+)?)\s*(horas?|hrs?|hs|h|dias?|semanas?)\b',texto):
            factor=168 if unidad.startswith('semana') else 24 if unidad.startswith('dia') else 1
            horas.append(float(numero.replace(',','.'))*factor)
        if re.search(r'\bmedio\s+dia\b',texto):
            horas.append(12.0)
        personas += [int(n) for n in re.findall(
            r'(?<![\w.,+\-])(\d+)\s*(?:personas?|habitantes?|residentes?|vecinos?|afectad[oa]s?)\b',texto)]
        # «Somos 20 familias» no declara 20 personas. Tampoco se aplica un factor.
        personas += [int(n) for n in re.findall(
            r'\bsomos\s+(\d+)(?=\s*(?:[.!?;,]|$)|\s+(?:personas?|habitantes?|residentes?|vecinos?|afectad[oa]s?|en|de|los|las)\b)',texto)]
    return horas, personas
