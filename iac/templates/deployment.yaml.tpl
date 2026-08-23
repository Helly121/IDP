apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ service_name }}
  labels:
    app: {{ service_name }}
    app.kubernetes.io/managed-by: academic-idp
    idp.academic/language: {{ language }}
spec:
  replicas: {{ replicas }}
  selector:
    matchLabels:
      app: {{ service_name }}
  template:
    metadata:
      labels:
        app: {{ service_name }}
    spec:
      containers:
        - name: {{ service_name }}
          image: ghcr.io/academic-idp/{{ service_name }}:latest
          ports:
            - containerPort: {{ port | default(8000) }}
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
          livenessProbe:
            httpGet:
              path: /health
              port: {{ port | default(8000) }}
            initialDelaySeconds: 15
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: {{ port | default(8000) }}
            initialDelaySeconds: 5
            periodSeconds: 10
          env:
            - name: APP_ENV
              value: "{{ environment | default('dev') }}"
