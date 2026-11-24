\getenv database_name POSTGRES_DB
\getenv app_password SYNCOPS_LAB_APP_PASSWORD
CREATE ROLE syncops_lab LOGIN PASSWORD :'app_password';
ALTER DATABASE :"database_name" OWNER TO syncops_lab;
REVOKE CONNECT ON DATABASE :"database_name" FROM PUBLIC;
