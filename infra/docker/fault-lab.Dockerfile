FROM postgres:16-alpine

COPY infra/docker/fault-lab-init.sql /docker-entrypoint-initdb.d/001_fault_lab.sql
