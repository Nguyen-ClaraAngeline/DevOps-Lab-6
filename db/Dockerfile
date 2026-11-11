FROM postgres:16.4-bookworm
COPY migrations /migrations
COPY migrate.sh /migrate.sh
USER postgres
ENTRYPOINT ["sh", "/migrate.sh"]