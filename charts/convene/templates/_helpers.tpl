{{/*
Expand the name of the chart.
*/}}
{{- define "convene.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "convene.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "convene.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: convene
{{- end }}

{{/*
Service-specific labels
*/}}
{{- define "convene.serviceLabels" -}}
{{ include "convene.labels" . }}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
{{- end }}

{{/*
Service-specific selector labels
*/}}
{{- define "convene.selectorLabels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
{{- end }}

{{/*
Image reference for a service.
If global.imageTag is set, it overrides the per-service tag (used by CI deploys).
*/}}
{{- define "convene.image" -}}
{{- $tag := .tag -}}
{{- if .root.Values.global.imageTag -}}
{{- $tag = .root.Values.global.imageTag -}}
{{- end -}}
{{ .root.Values.global.registryPrefix }}/{{ .svc }}:{{ $tag }}
{{- end }}

{{/*
PostgreSQL connection URL
*/}}
{{- define "convene.databaseUrl" -}}
postgresql+asyncpg://{{ .Values.postgres.credentials.username }}:{{ .Values.postgres.credentials.password }}@postgres.{{ .Release.Namespace }}.svc:5432/{{ .Values.postgres.credentials.database }}
{{- end }}

{{/*
PostgreSQL sync connection URL (for Alembic)
*/}}
{{- define "convene.databaseUrlSync" -}}
postgresql://{{ .Values.postgres.credentials.username }}:{{ .Values.postgres.credentials.password }}@postgres.{{ .Release.Namespace }}.svc:5432/{{ .Values.postgres.credentials.database }}
{{- end }}

{{/*
Redis connection URL
*/}}
{{- define "convene.redisUrl" -}}
redis://redis.{{ .Release.Namespace }}.svc:6379/0
{{- end }}
