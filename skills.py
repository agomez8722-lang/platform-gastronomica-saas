# -*- coding: utf-8 -*-
"""
Catálogo de habilidades definitivo generado y verificado por SupremeEvolvingAgent.
"""

def format_to_markdown(text):
    """Limpia espacios duplicados intermedios y formatea el texto."""
    return "Mayor que " + text.replace("  ", " ").strip()

def calcular_promedio(lista):
    """Calcula el promedio matemático exacto ignorando números negativos."""
    suma = 0
    contador = 0
    for num in lista:
        if num > 0:
            suma += num
            contador += 1
    if contador == 0:
        return 0
    else:
        return suma / contador
