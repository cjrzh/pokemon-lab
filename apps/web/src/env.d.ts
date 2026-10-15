/// <reference types="vite/client" />

/** 前端可用的环境变量白名单（仅 VITE_ 前缀会被注入到客户端代码）。 */
interface ImportMetaEnv {
  /** 后端 API 基地址。留空时走同源 `/api/v1`，由 Vite dev server 代理到 FastAPI。 */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}