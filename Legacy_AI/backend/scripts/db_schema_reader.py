from sqlalchemy import create_engine, inspect


def get_db_schema(db_url: str):
    """
    Fetch schema + relationships from any SQLAlchemy-supported DB URL
    """

    engine = create_engine(db_url)
    inspector = inspect(engine)

    SKIP_SCHEMAS = {"information_schema", "sys", "guest", "INFORMATION_SCHEMA", "SYS"}

    schema = {}
    all_schemas = inspector.get_schema_names()
    for db_schema in all_schemas:
        if db_schema in SKIP_SCHEMAS:
            continue
        for table_name in inspector.get_table_names(schema=db_schema):
            full_name = f"{db_schema}.{table_name}" if db_schema != "dbo" else table_name
            columns = inspector.get_columns(table_name, schema=db_schema)
            pk = inspector.get_pk_constraint(table_name, schema=db_schema)
            fks = inspector.get_foreign_keys(table_name, schema=db_schema)

            schema[full_name] = {
                "columns": [
                    {
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col["nullable"]
                    }
                    for col in columns
                ],
                "primary_key": pk.get("constrained_columns", []),
                "foreign_keys": [
                    {
                        "column": fk["constrained_columns"],
                        "references_table": fk["referred_table"],
                        "references_column": fk["referred_columns"],
                    }
                    for fk in fks
                ]
            }

    return schema


if __name__ == "__main__":
    db_url = "mssql+pyodbc://sa:khL27kRO1d7dnHHQn9v72bRWpXF@72.62.70.56:1436/NucleusOneDEV?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes"
    schema = get_db_schema(db_url)

    import json
    print(json.dumps(schema, indent=2))