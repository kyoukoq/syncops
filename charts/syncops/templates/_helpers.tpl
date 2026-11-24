{{- define "syncops.labels" -}}
app.kubernetes.io/name: syncops
app.kubernetes.io/instance: {{ .Release.Name | quote }}
{{- end -}}

{{- define "syncops.selector" -}}
{{ include "syncops.labels" .root }}
app.kubernetes.io/component: {{ .component | quote }}
{{- end -}}

{{- define "syncops.databaseEnv" -}}
- name: SYNCOPS_DATABASE_URL
  value: {{ printf "postgresql+psycopg://syncops@%s-db:5432/syncops?connect_timeout=3" .Release.Name | quote }}
- name: PGPASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Release.Name }}-db-app
      key: password
{{- end -}}

{{- define "syncops.mockTokenEnv" -}}
- name: SYNCOPS_MOCK_TOKEN
  valueFrom:
    secretKeyRef:
      name: {{ .Release.Name }}-mock-auth
      key: token
{{- end -}}

{{- define "syncops.podSecurity" -}}
runAsNonRoot: true
runAsUser: {{ .uid }}
runAsGroup: {{ .gid }}
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "syncops.containerSecurity" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}

{{- define "syncops.backendImage" -}}
image: {{ .Values.images.backend.reference | quote }}
imagePullPolicy: {{ .Values.images.backend.pullPolicy }}
{{- end -}}

{{- define "syncops.tempMount" -}}
- name: tmp
  mountPath: /tmp
{{- end -}}

{{- define "syncops.tempVolume" -}}
- name: tmp
  emptyDir:
    sizeLimit: 64Mi
{{- end -}}
