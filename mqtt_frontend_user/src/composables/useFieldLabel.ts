/**
 * 遥测字段中文翻译工具。
 * 从设备的 field_labels 映射中查找中文名称，找不到时降级为原始 key。
 */

export function useFieldLabel() {
  function translate(
    fieldLabels: Record<string, string> | null | undefined,
    key: string
  ): string {
    if (fieldLabels && fieldLabels[key]) return fieldLabels[key]
    return key
  }

  return { translate }
}
