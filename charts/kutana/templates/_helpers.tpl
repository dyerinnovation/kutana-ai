{{/*
Expand the name of the chart.
*/}}
{{- define "kutana.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "kutana.fullname" -}}
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
{{- define "kutana.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: kutana
{{- end }}

{{/*
Service-specific labels
*/}}
{{- define "kutana.serviceLabels" -}}
{{ include "kutana.labels" . }}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
{{- end }}

{{/*
Service-specific selector labels
*/}}
{{- define "kutana.selectorLabels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
{{- end }}

{{/*
Image reference for a service.
If global.imageTag is set, it overrides the per-service tag (used by CI deploys).
*/}}
{{- define "kutana.image" -}}
{{- $tag := .tag -}}
{{- if .root.Values.global.imageTag -}}
{{- $tag = .root.Values.global.imageTag -}}
{{- end -}}
{{ .root.Values.global.registryPrefix }}/{{ .svc }}:{{ $tag }}
{{- end }}

{{/*
PostgreSQL connection URL
*/}}
{{- define "kutana.databaseUrl" -}}
postgresql+asyncpg://{{ .Values.postgres.credentials.username }}:{{ .Values.postgres.credentials.password }}@postgres.{{ .Release.Namespace }}.svc:5432/{{ .Values.postgres.credentials.database }}
{{- end }}

{{/*
PostgreSQL sync connection URL (for Alembic)
*/}}
{{- define "kutana.databaseUrlSync" -}}
postgresql://{{ .Values.postgres.credentials.username }}:{{ .Values.postgres.credentials.password }}@postgres.{{ .Release.Namespace }}.svc:5432/{{ .Values.postgres.credentials.database }}
{{- end }}

{{/*
Redis connection URL
*/}}
{{- define "kutana.redisUrl" -}}
redis://redis.{{ .Release.Namespace }}.svc:6379/0
{{- end }}
