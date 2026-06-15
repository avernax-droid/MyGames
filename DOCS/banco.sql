
mysql -u root -pTonMix#25 --skip-column-names mygames_dev -e "
SELECT CONCAT('SHOW CREATE TABLE \`', table_name, '\`;') 
FROM information_schema.tables 
WHERE table_schema = 'mygames_dev';" | mysql -u root -pTonMix#25 mygames_dev > estrutura_real.sql

== comando para formatar o arquivo estrutura_real.sql
awk -F'\t' '{print $2}' estrutura_real.sql | sed 's/\\n/\n/g' > estrutura_formatada.sql

====================

mysql -u root -p mygames_dev --batch --raw -e "
SELECT * FROM (
    SELECT 
        IF(c.ORDINAL_POSITION = 1, c.TABLE_NAME, '') AS TABELA,
        c.COLUMN_NAME AS COLUNA,
        UPPER(c.COLUMN_TYPE) AS TIPO,
        CASE 
            WHEN c.COLUMN_KEY = 'PRI' AND c.EXTRA = 'auto_increment' THEN 'PK, AI'
            WHEN c.COLUMN_KEY = 'PRI' THEN 'PK'
            WHEN c.COLUMN_KEY = 'UNI' THEN 'UK'
            WHEN c.COLUMN_KEY = 'MUL' THEN 'FK'
            ELSE '-'
        END AS CHAVE,
        c.TABLE_NAME AS ORD_TABELA,
        c.ORDINAL_POSITION AS ORD_COLUNA,
        0 AS ORDEM_TIPO
    FROM INFORMATION_SCHEMA.COLUMNS c
    WHERE c.TABLE_SCHEMA = 'mygames_dev'

    UNION ALL

    SELECT 
        '----------' AS TABELA,
        '----------' AS COLUNA,
        '----------' AS TIPO,
        '----------' AS CHAVE,
        t.TABLE_NAME AS ORD_TABELA,
        999 AS ORD_COLUNA,
        1 AS ORDEM_TIPO
    FROM INFORMATION_SCHEMA.TABLES t
    WHERE t.TABLE_SCHEMA = 'mygames_dev'
) AS resultado
ORDER BY ORD_TABELA, ORDEM_TIPO, ORD_COLUNA;
" | column -t -s $'\t' > estrutura_tabelada.txt

