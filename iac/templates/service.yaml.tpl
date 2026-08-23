apiVersion: v1
kind: Service
metadata:
  name: {{ service_name }}-svc
  labels:
    app: {{ service_name }}
    app.kubernetes.io/managed-by: academic-idp
spec:
  type: ClusterIP
  selector:
    app: {{ service_name }}
  ports:
    - port: 80
      targetPort: {{ port | default(8000) }}
      protocol: TCP
      name: http
