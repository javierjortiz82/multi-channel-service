# Issue: Mensajes de Telegram Perdidos

## Fecha: 2026-01-06

## Problema
Los mensajes enviados por Telegram no reciben respuesta cuando el servicio `multi-channel-service` está dormido (scaled to 0).

## Causa Raíz
Combinación de dos configuraciones:

1. **`min-instances=0`** en Cloud Run
   - El servicio escala a 0 cuando no hay tráfico
   - Cold start toma ~3-10 segundos

2. **`drop_pending_updates=True`** en el webhook de Telegram
   - Configurado en `src/telegram_bot/main.py`
   - Descarta mensajes pendientes cuando el bot inicia
   - Diseñado para evitar spam de mensajes viejos

## Secuencia del Fallo
```
1. Usuario envía "hola" por Telegram
2. Telegram intenta entregar al webhook
3. Cloud Run inicia cold start (~5s)
4. Bot inicia con drop_pending_updates=True
5. Mensaje "hola" es DESCARTADO
6. Usuario no recibe respuesta
```

## Solución Aplicada
Cambiar `min-instances=0` a `min-instances=1` en `cloudbuild.yaml`:

```yaml
# Antes (MALO)
--min-instances=0 \

# Después (CORRECTO)
--min-instances=1 \
```

## Costo Adicional
- ~$5-10 USD/mes por mantener 1 instancia activa
- Justificación: UX crítica para bot de Telegram

## Alternativas Consideradas

### 1. Cambiar `drop_pending_updates=False`
- **Problema**: Acumula mensajes viejos durante downtime
- **Riesgo**: Spam de respuestas cuando el bot reinicia
- **Veredicto**: No recomendado

### 2. Usar Cloud Tasks para retry
- **Complejidad**: Alta
- **Latencia**: Añade delay
- **Veredicto**: Sobreingeniería para este caso

### 3. min-instances=1 (SELECCIONADO)
- **Beneficio**: Zero cold start, respuesta inmediata
- **Costo**: ~$5-10/mes
- **Veredicto**: Mejor balance costo/UX

## Verificación
```bash
# Verificar configuración
gcloud run services describe multi-channel-service \
  --region=us-central1 \
  --format="value(spec.template.spec.containerConcurrency,spec.template.metadata.annotations.'autoscaling.knative.dev/minScale')"

# Esperado: 80,1
```

## Prevención Futura
- [ ] Añadir alerta si min-instances < 1 para servicios críticos
- [ ] Documentar en CLAUDE.md
- [ ] Añadir test de integración que verifique respuesta < 5s
