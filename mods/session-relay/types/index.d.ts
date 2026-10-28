export type Relay = {
  /** 续篇 session 的标题 */
  title: string
  /** 续篇 session 的 id(local_…),没解析出来就是空串 */
  id: string
  /** 开出的时间(ms) */
  at: number
  /** 为什么开:cold-event(冷 session 收到自动回报)/ button(勾哥按了按钮)/ command(/relay-now) */
  reason: string
}

declare module 'claude-code' {
  interface PluginState {
    'yide': {
      relay: Relay | null
      /** 上下文 token 数(≥ FAT_CTX 时才记,否则 0) */
      fat: number
      isHidden: boolean
    }
  }
}
