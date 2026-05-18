# Plan 5: 前端（地图 + 日志 + 控制）

## 前置
Plan 1 + 4 完成，后端有世界数据和 WebSocket 推送能力。

## 目标
实现 Web 前端：Canvas 2D 全局地图 + 左下角日志框 + 模拟控制。

## 产出文件
```
client/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   └── ws.ts               # WebSocket 客户端
│   ├── stores/
│   │   └── world.ts            # Zustand: world state, agents, logs
│   ├── components/
│   │   ├── MapCanvas.tsx        # Canvas 2D 地图渲染
│   │   ├── LogPanel.tsx         # 左下角日志面板
│   │   ├── AgentDetail.tsx      # 点击人物弹出详情
│   │   ├── SimControls.tsx      # 播放/暂停/加速 控制
│   │   └── TimeDisplay.tsx      # 当前时间显示
│   └── styles/
│       └── index.css            # Tailwind 入口
```

## 详细步骤

### 5.1 React 项目初始化
- Vite + React + TypeScript
- Tailwind CSS + shadcn/ui
- Zustand 状态管理

### 5.2 WebSocket 连接
- 连接 `ws://localhost:8000/ws/world/{id}`
- 接收 tick 推送：`{ tick, day, time_of_day, agent_updates: [...], events: [...] }`
- 收到后更新 Zustand store

### 5.3 Zustand Store
```typescript
interface WorldStore {
  world: { grid_size: number; tick: number; day: number; time_of_day: string }
  locations: Location[]        // 所有格子
  agents: Agent[]              // 所有角色
  logs: LogEntry[]             // 日志消息
  selectedAgent: string | null // 当前聚焦的角色 id

  focusAgent: (id: string) => void
  addLog: (entry: LogEntry) => void
}
```

### 5.4 MapCanvas（核心渲染）
- Canvas 2D，绘制 N×N 方格地图
- **格子渲染**：
  - 山地 → 灰色填充
  - 平地 → 浅绿
  - 建筑 → 方块（带文字标注）
  - 城市 → 粗线方块
- **角色渲染**：
  - T1 → 大圆点 + 名字标签（亮色）
  - T2 → 中圆点（普通色）
  - T3 → 小圆点（暗色）
  - 行进中 → 圆点沿路径移动动画
- **交互**：
  - 鼠标滚轮缩放
  - 拖拽平移
  - 点击角色 → focusAgent + 弹出 AgentDetail
  - 点击地点 → 显示地点信息

### 5.5 LogPanel（左下角日志）
- 固定在左下角，半透明背景
- 滚动列表，新消息从底部追加
- 格式：`[第X天 午时] 令狐冲 - 在练剑场练剑`
- 点击条目 → 地图自动聚焦到该角色位置 + 缩放
- 重大事件高亮显示

### 5.6 SimControls + TimeDisplay
- 播放/暂停按钮
- 速度控制：1x, 2x, 5x
- 当前时间：`第3天 辰时 (tick 38)`

### 5.7 AgentDetail 弹出面板
- 点击角色后弹出
- 显示：名字、角色、等级、当前状态、今日计划、近期记忆摘要
- 关闭按钮

## 验证
- 打开页面，看到华山派 16×16 地图，建筑和地形正确显示
- 启动模拟，角色圆点在地图上移动
- 日志面板实时显示角色行为
- 点击日志条目，地图聚焦到对应角色
- 点击角色圆点，弹出详情面板
