apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ service_name }}-ingress
  labels:
    app: {{ service_name }}
    app.kubernetes.io/managed-by: academic-idp
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "false"
spec:
  ingressClassName: nginx
  rules:
    - host: {{ service_name }}.idp.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {{ service_name }}-svc
                port:
                  number: 80
