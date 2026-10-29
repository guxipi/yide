export type Relay = {
  /** 续篇 session 的标题(占位时为空串) */
  title: string
  /** 续篇 session 的 id(local_…),没解析出来或还在占位就是空串 */
  id: string
  /** 开出(或占位)的时间(ms) */
  at: number
  /** 为什么开:cold-event(冷 session 收到自动回报)/ command(/relay-now)/ pending(正在开的占位) */
  reason: string
}

declare module 'claude-code' {
  interface PluginState {
    'yide': {
      relay: Relay | null
      isHidden: boolean
    }
  }
}
