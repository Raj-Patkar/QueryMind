export function getTableColumns(table) {
  if (Array.isArray(table.columns)) return table.columns.map((column) => typeof column === 'string' ? column : column.name)
  return []
}

export function formatSql(sql = '') {
  return sql
    .replace(/\s+(FROM|WHERE|GROUP BY|ORDER BY|LIMIT|HAVING|JOIN|LEFT JOIN|INNER JOIN|ON)\s+/gi, '\n$1 ')
    .replace(/\s+(AND|OR)\s+/gi, '\n  $1 ')
    .trim()
}

export function statusLabel(status) {
  return ({
    executed: 'Executed',
    sql_ready_for_review: 'Validated',
    invalid_sql: 'Blocked by validator',
    manual_review: 'Needs review',
    clarification_needed: 'Clarification needed',
    unanswerable: 'Not answerable',
    service_unavailable: 'Unavailable',
  })[status] || status || 'Completed'
}
