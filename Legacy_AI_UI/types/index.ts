export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface UserPublic {
  id?: string
  organization_id: string
  name: string
  email: string
  role: 'user' | 'org_manager' | 'org_admin' | 'super_admin' | string
  created_at: string
  avatar_url?: string | null
  waiting_approval?: 'approved' | 'waiting' | 'disapproved' | string
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  user: UserPublic;
  db_conn_ids: string[];
}

export interface PermissionsResponse {
  user_id: string;
  role_stored: string;
  is_super_admin: boolean;
  is_org_admin?: boolean;
  resolved_permissions: Record<string, boolean>;
}

export interface AssignableRole {
  name: string;
  label: string;
  is_admin: boolean;
}

export interface PermissionDefinition {
  name: string;
  label: string;
  description: string;
  resource: string;
}

export interface OrgRolePermissions {
  organization_id: string;
  role: string;
  label: string;
  permission_names: string[];
  is_override: boolean;
  updated_at?: string | null;
}

export interface OrganizationPublic {
  id?: string;
  name: string;
  description?: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface TeamPublic {
  id?: string;
  organization_id: string;
  name: string;
  description?: string;
  member_ids: string[];
  permissions?: string[];
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface AgentPublic {
  id?: string
  organization_id: string
  name: string
  prompt: string
  guardrails: string
  description?: string
  model?: string | null
  user_description?: string
  instructions?: string
  tool_ids: string[]
  rag_ids: string[]
  mcp_server_ids: string[]
  connector_ids: string[]
  connectors?: Array<{ id: string; provider_id: string; name: string; icon?: string }>
  is_active?: boolean
  avatar_type?: AgentAvatarType
  avatar_value?: string | null
  avatar_url?: string | null
  created_by: string
  created_at: string
  owner_scope: 'user' | 'organization' | 'selected_users' | 'team'
  allowed_user_ids: string[]
  team_id?: string | null
}

export type AgentAvatarType = "color" | "emoji" | "sticker" | "image" | "brand";

export interface ProjectFilePublic {
  id: string
  filename: string
  original_filename: string
  file_type: string
  file_size: number
  content?: string | null
  content_summary?: string | null
  uploaded_by: string
  uploaded_at: string
}

export interface ProjectChatMessagePublic {
  id: string
  project_id: string
  organization_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  auth_errors?: any[]
  user_id?: string | null
  created_at: string
}

export interface ProjectPublic {
  id?: string
  organization_id: string
  name: string
  description?: string | null
  system_prompt: string
  guardrails?: string | null
  tool_ids: string[]
  connector_ids: string[]
  connectors?: Array<{ id: string; provider_id: string; name: string; icon?: string; permissions?: Record<string, string[]> }>
  connector_permissions?: Record<string, ConnectorPermissions>
  knowledge_base_ids?: string[]
  files: ProjectFilePublic[]
  created_by: string
  created_at: string
  updated_at?: string | null
  owner_scope: 'user' | 'organization' | 'selected_users' | 'team'
  allowed_user_ids: string[]
  team_id?: string | null
}

export interface ProjectCreateInput {
  organization_id: string
  name: string
  description?: string
  system_prompt?: string
  guardrails?: string
  tool_ids?: string[]
  connector_ids?: string[]
  connector_permissions?: Record<string, ConnectorPermissions>
  knowledge_base_ids?: string[]
  owner_scope?: 'user' | 'organization' | 'selected_users' | 'team'
  allowed_user_ids?: string[]
  team_id?: string
}

export interface ProjectUpdateInput {
  name?: string
  description?: string
  system_prompt?: string
  guardrails?: string
  tool_ids?: string[]
  connector_ids?: string[]
  connector_permissions?: Record<string, ConnectorPermissions>
  knowledge_base_ids?: string[]
  owner_scope?: 'user' | 'organization' | 'selected_users' | 'team'
  allowed_user_ids?: string[]
  team_id?: string
}

export interface ProjectChatResponse {
  reply: string
  session_id: string
  name?: string | null
  auth_errors?: Array<Record<string, any>>
}

export interface ToolPublic {
  id?: string
  organization_id: string
  agent_id: string
  agent_name?: string
  agent_avatar_type?: AgentAvatarType
  agent_avatar_value?: string | null
  agent_avatar_url?: string | null
  name?: string
  user_description?: string
  tool_id: string
  db_conn_id?: string
  has_custom_credentials?: boolean
  created_at: string
}

export interface DbConnectionPublic {
  id?: string;
  organization_id: string;
  name?: string;
  connection_type?: string;
  connection_string: string;
  created_at: string;
}

export interface FirebaseConnectionInput {
  service_account: Record<string, unknown>;
  database_id?: string;
}

export interface DbConnectionTargetInput {
  connection_string?: string;
  firebase?: FirebaseConnectionInput;
}

export interface DbConnectionMetadataInput {
  name?: string;
  connection_type?: string;
}

export interface ToolRegistryPublic {
  id?: string;
  name: string;
  description?: string;
  type: "db" | "db_query" | "http" | "rag" | "custom" | string;
  is_active: boolean;
  tool_schema?: Record<string, unknown>;
  created_at: string;
}

export interface TraceListItem {
  id: string;
  timestamp: string;
  name: string;
  input?: unknown;
  output?: unknown;
  session_id?: string;
  user_id?: string;
  metadata?: Record<string, unknown>;
  tags: string[];
  latency?: number;
  total_cost?: number;
  agent_name?: string;
}

export type TracePublic = TraceListItem;

export interface ObservationItem {
  id: string;
  trace_id?: string;
  type: "generation" | "span" | "event" | string;
  name: string;
  start_time?: string;
  end_time?: string;
  input?: unknown;
  output?: unknown;
  metadata?: Record<string, unknown>;
  parent_observation_id?: string;
  model?: string;
  usage?: Record<string, unknown>;
  calculated_total_cost?: number;
  latency?: number;
}

export type TraceObservation = ObservationItem;

export interface TraceDetail extends TraceListItem {
  observations: ObservationItem[];
}

export interface TraceStats {
  total_traces: number;
  total_cost: number;
  total_input_tokens: number;
  total_output_tokens: number;
  agent_breakdown: Array<{
    agent_name: string;
    trace_count: number;
    total_cost: number;
    total_tokens: number;
  }>;
  user_breakdown: Array<{
    user_id: string;
    user_name?: string | null;
    user_email?: string | null;
    trace_count: number;
    total_cost: number;
    total_tokens: number;
  }>;
}

export interface SessionPublic {
  thread_id: string;
  organization_id: string;
  name: string | null;
  available_agents: Array<{
    agent_id: string;
    name: string;
    description?: string;
    tool_count: number;
  }>;
  created_at: string;
}

/** A connector tool call that failed because its OAuth token is expired/revoked. */
export interface ConnectorAuthErrorInfo {
  connector_id?: string | null;
  provider_id?: string | null;
  display_name?: string | null;
  fn_name?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  trace_id?: string;
  agent_id?: string;
  /** Names of documents the user attached to this message (shown as chips in the bubble). */
  attachments?: string[];
  /** Set when a tool call behind this message failed on a dead connector token. */
  auth_errors?: ConnectorAuthErrorInfo[];
}

export interface ChatResponse {
  thread_id: string;
  response: string;
  messages_count: number;
  name?: string | null;
  auth_errors?: ConnectorAuthErrorInfo[];
}

export type SessionChatResponse = ChatResponse;

/** Live progress during a chat turn, driven by real backend SSE events (not simulated). */
export type LiveActivity =
  | { type: "routing"; agentId: string; label: string }
  | { type: "tool_call"; kind: "connector" | "mcp" | "tool"; label: string }
  | null;

export interface DirectChatResponse {
  session_id: string;
  reply: string;
  trace_id?: string;
  name?: string | null;
  auth_errors?: ConnectorAuthErrorInfo[];
}

export interface DbSchema {
  kind: "sql" | "mongo" | "firebase";
  dialect?: string;
  tables?: Record<
    string,
    Array<{ name: string; type: string; nullable: boolean }>
  >;
  databases?: Record<string, Record<string, Record<string, string>>>;
  database?: "firestore" | string;
  project_id?: string;
  database_id?: string;
  collections?: Record<string, DbConnectionPreviewCollection>;
}

export interface DbConnectionPreviewTable {
  columns: Array<{ name: string; type: string; nullable: boolean }>;
  description?: string | null;
}

export interface DbConnectionPreviewCollection {
  fields?: Record<string, unknown>;
  description?: string | null;
}

export interface DbConnectionPreviewResponse {
  kind: "sql" | "mongo" | "firebase";
  dialect?: string;
  database?: "firestore" | string;
  project_id?: string;
  database_id?: string;
  table_count: number;
  described_count: number;
  truncated: boolean;
  formatted_connection_string?: string;
  tables?: Record<string, DbConnectionPreviewTable>;
  databases?: Record<string, Record<string, DbConnectionPreviewCollection>>;
  collections?: Record<string, DbConnectionPreviewCollection>;
}

export interface ChatMessageHistory {
  role: "user" | "assistant";
  content: string;
  agent_id?: string;
  timestamp: string;
}

export interface SessionListItem {
  thread_id: string;
  organization_id: string;
  user_id: string;
  name?: string | null;
  epoch: number;
  agent_ids: string[];
  created_at?: string;
}

export type ChatSessionHistory = SessionListItem;

export type NotificationType =
  | "agent"
  | "tool"
  | "alert"
  | "success"
  | "system";

export interface NotificationPublic {
  id: string;
  organization_id: string;
  user_id?: string | null;
  type: NotificationType;
  title: string;
  message: string;
  read: boolean;
  created_at: string;
}

export interface OrgSettings {
  organization_id: string;
  maintenance_mode: boolean;
  require_2fa: boolean;
  session_timeout_enabled: boolean;
  session_duration: string;
  audit_logging: boolean;
  default_model: string;
  updated_at?: string | null;
}

export type OrgSettingsUpdate = Partial<
  Omit<OrgSettings, "organization_id" | "updated_at">
>;

export interface ConversationTurn {
  type: "turn";
  human_message: string;
  agent_message: string;
  timestamp: string;
  tool_called?: boolean;
  tool_name?: string;
  auth_errors?: ConnectorAuthErrorInfo[];
}

export interface ConversationSummary {
  type: "summary";
  content: string;
  timestamp: string;
}

export type ConversationEntry = ConversationTurn | ConversationSummary;

export interface AgentHistory {
  agent_id: string;
  total_messages: number;
  total_summaries: number;
  conversations: ConversationEntry[];
  created_at?: string;
  updated_at?: string;
}

export interface SessionHistoryResponse {
  thread_id: string;
  organization_id: string;
  user_id: string;
  name?: string | null;
  epoch: number;
  agents: AgentHistory[];
  created_at?: string;
}

// ── Google Drive ────────────────────────────────────────────────────────────

export interface GoogleAuthUrlResponse {
  url: string;
}

export interface AuthStatusResponse {
  connected: boolean;
}

export interface DriveCredentialsStatus {
  has_credentials: boolean;
  client_id?: string;
  redirect_uri: string;
}

export interface DriveFile {
  id: string;
  name: string;
  mime_type: string;
  size?: number;
  created_at?: string;
  modified_at?: string;
}

export interface CreateDriveFilePayload {
  name: string;
  mime_type?: string;
  content?: string;
}

export interface RenameDriveFilePayload {
  name: string;
}

export interface ShareDriveFilePayload {
  email: string;
  role?: "reader" | "writer" | "commenter";
}

// ── OneDrive ────────────────────────────────────────────────────────────

export interface MicrosoftAuthUrlResponse {
  url: string;
}

export interface MicrosoftAuthStatusResponse {
  connected: boolean;
}

export interface MicrosoftCredentialsStatus {
  has_credentials: boolean;
  client_id?: string;
  redirect_uri: string;
}

// ── MCP ──────────────────────────────────────────────────────────────────────

export interface McpToolSpec {
  name: string;
  description: string;
  input_schema?: Record<string, unknown>;
}

export interface McpServerPublic {
  id?: string;
  organization_id: string;
  agent_id?: string | null;
  registry_key?: string;
  auth_type: "none" | "bearer" | "oauth" | string;
  name?: string;
  user_description?: string;
  connection_string?: string;
  transport?: "stdio" | "streamable_http" | "sse" | "websocket" | string;
  tools: McpToolSpec[];
  tool_count: number;
  status: "pending" | "connected" | "error" | string;
  last_error?: string;
  discovered_at?: string;
  timeout: number;
  is_active: boolean;
  created_at: string;
}

// ── Orchestrations ────────────────────────────────────────────────────────────

export interface PendingReauthInfo {
  connector_id?: string | null;
  provider_id?: string | null;
  display_name?: string | null;
  fn_name?: string | null;
}

export interface BranchStatusPublic {
  branch_id: string;
  status: string;
  human_question?: string | null;
  human_asked_by_agent?: string | null;
  pending_reauth?: PendingReauthInfo | null;
  pending_agents: string[];
  label?: string | null;
}

export interface AgentConnectionOut {
  from_agent_id: string;
  to_agent_id: string;
  label?: string;
}

export interface AgentBriefPublic {
  agent_id: string;
  name: string;
  description?: string;
}

/** "sequential" = the original edge-driven flow (Start → A → B → End).
 *  "supervisor" = a hardcoded Supervisor is the entry point and routes each
 *  request to whichever connected agent fits. Absent on documents saved before
 *  supervisor mode existed, which the backend reads as "sequential". */
export type OrchestrationMode = "sequential" | "supervisor";

export interface SupervisorConfig {
  /** Max agent invocations in one turn. */
  max_hops: number;
  max_visits_per_agent: number;
  /** How many agents may decline in a row before the turn gives up. */
  max_consecutive_handbacks: number;
  /** Pass the previous turn's agent to the Supervisor as a continuity hint. */
  sticky_routing: boolean;
  /** false = routing only: the Supervisor may not answer questions itself. */
  allow_direct_answer: boolean;
  custom_instructions: string;
  model?: string | null;
}

export interface OrchestrationPublic {
  id: string;
  organization_id: string;
  name: string;
  description?: string;
  mode: OrchestrationMode;
  /** null in supervisor mode — the Supervisor is the entry point and is not an agent. */
  main_agent_id: string | null;
  sub_agent_ids: string[];
  connections: AgentConnectionOut[];
  supervisor_config?: SupervisorConfig | null;
  max_depth: number;
  timeout_sec: number;
  agents: AgentBriefPublic[];
  created_by: string;
  created_at: string;
  owner_scope: "user" | "organization" | "selected_users" | "team";
  allowed_user_ids: string[];
  team_id?: string | null;
}

export interface OrchestrationCreate {
  name: string;
  description?: string;
  mode?: OrchestrationMode;
  /** Required in sequential mode, omitted in supervisor mode. */
  main_agent_id?: string;
  sub_agent_ids: string[];
  connections: AgentConnectionOut[];
  supervisor_config?: SupervisorConfig;
  max_depth?: number;
  timeout_sec?: number;
  owner_scope?: "user" | "organization" | "selected_users" | "team";
  allowed_user_ids?: string[];
  team_id?: string | null;
}

export interface OrchestrationUpdate {
  name?: string;
  description?: string;
  mode?: OrchestrationMode;
  main_agent_id?: string;
  sub_agent_ids?: string[];
  connections?: AgentConnectionOut[];
  supervisor_config?: SupervisorConfig;
  max_depth?: number;
  timeout_sec?: number;
  owner_scope?: "user" | "organization" | "selected_users" | "team";
  allowed_user_ids?: string[];
  team_id?: string | null;
}

export interface OrchestrationChatResponse {
  response: string;
  orchestration_id: string;
  session_id: string;
  name?: string | null;
  status: string;
  run_id?: string | null;
  human_question?: string | null;
  pending_reauth?: PendingReauthInfo | null;
}

export interface AgentStepPublic {
  agent_id: string;
  agent_name: string;
  /** 'handback' entries are internal control transfers and are filtered out by
   *  the backend; the chat renderer skips them too, so a stale client can never
   *  surface one as if it were an answer. */
  status: "complete" | "running" | "handback";
  output?: string | null;
  branch_id?: string | null;
}

export interface OrchestrationRunStatus {
  run_id: string;
  orchestration_id: string;
  status: string; // loading | running | routing | waiting_for_human | complete | failed | timeout
  current_agent_id?: string | null;
  current_agent_name?: string | null;
  steps: AgentStepPublic[];
  human_question?: string | null;
  pending_reauth?: PendingReauthInfo | null;
  final_response?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  branches: BranchStatusPublic[];
}

// ── Orchestration Session History ────────────────────────────────────────────

export interface OrchestrationHistoryUserInput {
  type: "user_input";
  user_input: string;
  timestamp: string;
  branch_id?: string;
}

export interface OrchestrationHistoryNode {
  type: "node";
  node_name: string;
  node_num: number;
  tools_called: string[];
  node_output: string;
  timestamp: string;
  branch_id?: string;
}

export interface OrchestrationHistoryHitl {
  type: "hitl";
  user_input: string;
  node_name: string;
  node_num: number;
  node_output: string;
  timestamp: string;
  branch_id?: string;
}

export type OrchestrationHistoryEntry =
  | OrchestrationHistoryUserInput
  | OrchestrationHistoryNode
  | OrchestrationHistoryHitl;

export interface OrchestrationSessionHistoryResponse {
  conversations: OrchestrationHistoryEntry[];
  pending_run_id?: string | null;
  branch_id?: string | null;
  pending_branches: BranchStatusPublic[];
}

export interface OrchestrationSessionBrief {
  session_id: string;
  name?: string | null;
  last_message?: string | null;
  total_messages: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface OrchestrationSessionListResponse {
  orchestration_id: string;
  sessions: OrchestrationSessionBrief[];
}

export interface OrchestrationInitResponse {
  session_id: string;
  orchestration_id: string;
  status: string;
  main_agent_id?: string | null;
  main_agent_name?: string | null;
}

// ── MCP ──────────────────────────────────────────────────────────────────────

export interface McpAgentToolPublic {
  id?: string;
  organization_id: string;
  agent_id: string;
  mcp_server_id: string;
  mcp_server_name?: string;
  tool_name: string;
  created_at: string;
}

export interface McpCatalogEntry {
  key: string;
  name: string;
  description: string;
  category?: string;
  transport?: string;
  connection_string: string;
  requires: string[];
  source: string;
  homepage?: string;
}

export interface McpTestConnectionResult {
  ok: boolean;
  transport?: string;
  tools: McpToolSpec[];
  tool_count: number;
  error?: string;
}

// ── Embeddable chatbot widgets ───────────────────────────────────────────────

export type WidgetSourceType = "single_agent" | "supervisor";
export type WidgetPosition = "bottom-right" | "bottom-left";

export type WidgetFontWeight = "normal" | "medium" | "bold";
export type WidgetLauncherShape = "circle" | "rounded-square";
export type WidgetLauncherIcon = "chat" | "message" | "robot" | "custom";
export type WidgetLauncherHoverEffect = "none" | "scale" | "shadow" | "both";
export type WidgetShadowStyle = "none" | "soft" | "medium" | "strong";
export type WidgetBubbleStyle = "rounded" | "square" | "soft";
export type WidgetSendButtonShape = "circle" | "rounded" | "square";
export type WidgetSpacingDensity = "compact" | "comfortable" | "spacious";
export type WidgetTextDirection = "auto" | "ltr" | "rtl";
export type WidgetAnimationStyle = "none" | "fade" | "slide" | "scale";

export interface WidgetLocaleCopy {
  header_title?: string | null;
  header_subtitle?: string | null;
  greeting_message?: string | null;
  input_placeholder?: string | null;
  loading_text?: string | null;
  empty_state_text?: string | null;
  error_message_text?: string | null;
  offline_message?: string | null;
  quick_replies?: string[] | null;
}

export interface WidgetBranding {
  theme_color: string;
  position: WidgetPosition;
  header_title: string;
  header_subtitle?: string | null;
  header_logo_url?: string | null;
  header_text_color: string;
  header_bg_color?: string | null;
  greeting_message: string;
  dark_mode: boolean;
  font_family: string;
  font_size_base: number;
  font_weight: WidgetFontWeight;
  secondary_color: string;
  background_color?: string | null;
  text_color?: string | null;
  border_color?: string | null;
  assistant_avatar_url?: string | null;
  user_avatar_url?: string | null;
  show_avatars_in_messages: boolean;
  user_bubble_color?: string | null;
  assistant_bubble_color?: string | null;
  show_timestamps: boolean;
  input_placeholder: string;
  send_button_color?: string | null;
  loading_text: string;
  empty_state_text: string;
  error_message_text: string;
  quick_replies: string[];
  show_branding: boolean;
  custom_css?: string | null;
  text_direction?: WidgetTextDirection;
  locales?: Record<string, WidgetLocaleCopy>;
}

export interface WidgetBrandingInput {
  theme_color?: string;
  position?: WidgetPosition;
  header_title?: string;
  header_subtitle?: string | null;
  header_logo_url?: string | null;
  header_text_color?: string;
  header_bg_color?: string | null;
  greeting_message?: string;
  dark_mode?: boolean;
  font_family?: string;
  font_size_base?: number;
  font_weight?: WidgetFontWeight;
  secondary_color?: string;
  background_color?: string | null;
  text_color?: string | null;
  border_color?: string | null;
  assistant_avatar_url?: string | null;
  user_avatar_url?: string | null;
  show_avatars_in_messages?: boolean;
  user_bubble_color?: string | null;
  assistant_bubble_color?: string | null;
  show_timestamps?: boolean;
  input_placeholder?: string;
  send_button_color?: string | null;
  loading_text?: string;
  empty_state_text?: string;
  error_message_text?: string;
  quick_replies?: string[];
  show_branding?: boolean;
  custom_css?: string | null;
  text_direction?: WidgetTextDirection;
  locales?: Record<string, WidgetLocaleCopy>;
}

export interface WidgetLayout {
  widget_width: number;
  widget_height: number;
  widget_min_width: number;
  widget_min_height: number;
  widget_max_width: number;
  widget_max_height: number;
  launcher_size: number;
  launcher_shape: WidgetLauncherShape;
  launcher_icon: WidgetLauncherIcon;
  launcher_icon_url?: string | null;
  launcher_hover_effect: WidgetLauncherHoverEffect;
  offset_x: number;
  offset_y: number;
  border_radius: number;
  shadow_style: WidgetShadowStyle;
  bubble_style: WidgetBubbleStyle;
  send_button_shape: WidgetSendButtonShape;
  spacing_density: WidgetSpacingDensity;
  animation_style: WidgetAnimationStyle;
  mobile_full_screen: boolean;
  mobile_breakpoint_px: number;
}

export interface WidgetLayoutInput {
  widget_width?: number;
  widget_height?: number;
  widget_min_width?: number;
  widget_min_height?: number;
  widget_max_width?: number;
  widget_max_height?: number;
  launcher_size?: number;
  launcher_shape?: WidgetLauncherShape;
  launcher_icon?: WidgetLauncherIcon;
  launcher_icon_url?: string | null;
  launcher_hover_effect?: WidgetLauncherHoverEffect;
  offset_x?: number;
  offset_y?: number;
  border_radius?: number;
  shadow_style?: WidgetShadowStyle;
  bubble_style?: WidgetBubbleStyle;
  send_button_shape?: WidgetSendButtonShape;
  spacing_density?: WidgetSpacingDensity;
  animation_style?: WidgetAnimationStyle;
  mobile_full_screen?: boolean;
  mobile_breakpoint_px?: number;
}

export interface TargetedGreeting {
  path_pattern: string;
  greeting: string;
}

export interface WidgetTriggers {
  auto_open: boolean;
  auto_open_delay_ms: number;
  open_on_scroll_percent?: number | null;
  targeted_greetings: TargetedGreeting[];
}

export interface WidgetTriggersInput {
  auto_open?: boolean;
  auto_open_delay_ms?: number;
  open_on_scroll_percent?: number | null;
  targeted_greetings?: TargetedGreeting[];
}

export interface WidgetBehavior {
  response_language: string;
  tone_instructions?: string | null;
  welcome_sound: boolean;
  allow_attachments?: boolean;
  rich_messages?: boolean;
}

export interface WidgetBehaviorInput {
  response_language?: string;
  tone_instructions?: string | null;
  welcome_sound?: boolean;
  allow_attachments?: boolean;
  rich_messages?: boolean;
}

export interface DaySchedule {
  enabled: boolean;
  start: string;
  end: string;
}

export type DayKey = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";

export interface WidgetAvailability {
  enabled: boolean;
  timezone: string;
  schedule: Record<DayKey, DaySchedule>;
  offline_message: string;
}

export interface WidgetAvailabilityInput {
  enabled?: boolean;
  timezone?: string;
  schedule?: Partial<Record<DayKey, Partial<DaySchedule>>>;
  offline_message?: string;
}

export interface WidgetAccessibility {
  reduced_motion: boolean;
  high_contrast: boolean;
  large_text: boolean;
}

export interface WidgetAccessibilityInput {
  reduced_motion?: boolean;
  high_contrast?: boolean;
  large_text?: boolean;
}

export type LeadFieldType = "text" | "email" | "phone";

export interface LeadField {
  field_name: string;
  label: string;
  field_type: LeadFieldType;
  required: boolean;
}

export interface WidgetWebhookTarget {
  url?: string | null;
  has_secret: boolean;
  is_active: boolean;
}

export interface WidgetWebhookTargetInput {
  url?: string | null;
  secret?: string;
  is_active?: boolean;
}

export interface WidgetWebhooks {
  conversation_started: WidgetWebhookTarget;
  lead_captured: WidgetWebhookTarget;
  message_sent: WidgetWebhookTarget;
  feedback_submitted: WidgetWebhookTarget;
}

export interface WidgetWebhooksInput {
  conversation_started?: WidgetWebhookTargetInput;
  lead_captured?: WidgetWebhookTargetInput;
  message_sent?: WidgetWebhookTargetInput;
  feedback_submitted?: WidgetWebhookTargetInput;
}

export interface WidgetSecurity {
  allowed_origins: string[];
  require_api_key: boolean;
  has_api_key: boolean;
  rate_limit_per_minute?: number | null;
  retention_days?: number | null;
}

export interface WidgetSecurityInput {
  allowed_origins?: string[];
  require_api_key?: boolean;
  // null clears the widget-specific limit; undefined leaves it unchanged.
  rate_limit_per_minute?: number | null;
  retention_days?: number | null;
}

export interface WidgetConfigPublic {
  id?: string;
  organization_id: string;
  name: string;
  source_type: WidgetSourceType;
  agent_id?: string | null;
  is_enabled: boolean;
  branding: WidgetBranding;
  layout: WidgetLayout;
  triggers: WidgetTriggers;
  behavior: WidgetBehavior;
  availability: WidgetAvailability;
  accessibility: WidgetAccessibility;
  lead_fields: LeadField[];
  webhooks: WidgetWebhooks;
  security: WidgetSecurity;
  created_by: string;
  created_at: string;
  updated_at: string;
  // Draft/publish state -- the sections above always reflect the DRAFT;
  // visitors instead see whatever was last published.
  published_version?: number | null;
  published_at?: string | null;
  has_unpublished_changes: boolean;
}

export interface WidgetVersionListItem {
  version: number;
  published_by: string;
  published_by_name?: string | null;
  published_at: string;
  restored_from_version?: number | null;
  changed_sections?: string[];
}

export interface WidgetWebhookDeliveryItem {
  id: string;
  kind?: "event" | "test" | "replay" | string;
  can_replay?: boolean;
  event: string;
  url: string;
  ok: boolean;
  attempts: number;
  status_code?: number | null;
  error?: string | null;
  created_at: string;
}

export interface WidgetWebhookDeliveryResult {
  ok: boolean;
  status_code?: number | null;
  error?: string | null;
}

export interface WidgetWebhookDeliveriesResponse {
  items: WidgetWebhookDeliveryItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface WidgetConfigCreateInput {
  organization_id: string;
  name: string;
  source_type: WidgetSourceType;
  agent_id?: string | null;
  branding?: WidgetBrandingInput;
  layout?: WidgetLayoutInput;
  triggers?: WidgetTriggersInput;
  behavior?: WidgetBehaviorInput;
  availability?: WidgetAvailabilityInput;
  accessibility?: WidgetAccessibilityInput;
  lead_fields?: LeadField[];
  webhooks?: WidgetWebhooksInput;
  security?: WidgetSecurityInput;
}

export interface WidgetConfigUpdateInput {
  name?: string;
  source_type?: WidgetSourceType;
  agent_id?: string | null;
  branding?: WidgetBrandingInput;
  layout?: WidgetLayoutInput;
  triggers?: WidgetTriggersInput;
  behavior?: WidgetBehaviorInput;
  availability?: WidgetAvailabilityInput;
  accessibility?: WidgetAccessibilityInput;
  lead_fields?: LeadField[];
  webhooks?: WidgetWebhooksInput;
  security?: WidgetSecurityInput;
  is_enabled?: boolean;
}

export interface WidgetApiKeyResponse {
  widget_id: string;
  api_key: string;
}

export interface WidgetImageUploadResponse {
  url: string;
}

export interface WidgetPreviewTokenResponse {
  widget_id: string;
  preview_token: string;
  expires_at: string;
}

export interface WidgetSessionListItem {
  visitor_session_id: string;
  created_at: string;
  last_active_at: string;
  status: string;
  origin?: string | null;
  has_lead: boolean;
  lead_values?: Record<string, string> | null;
}

export interface WidgetDayCount {
  date: string;
  count: number;
}

export interface WidgetAnalytics {
  total_sessions: number;
  sessions_today: number;
  leads_captured: number;
  feedback_up: number;
  feedback_down: number;
  sessions_by_day: WidgetDayCount[];
}

// ── Schedules ──────────────────────────────────────────────────────────────

export type RecurrenceKind =
  | "once"
  | "daily"
  | "weekly"
  | "monthly"
  | "always"
  | "custom";

export interface RecurrenceConfig {
  kind: RecurrenceKind;
  time_of_day?: string | null; // "HH:MM", local to `timezone` — daily/weekly/monthly
  day_of_week?: number[]; // ISO 1=Mon..7=Sun — weekly
  day_of_month?: number | null; // 1-31, or -1 for "last day" — monthly
  interval_minutes?: number | null; // "always" — minimum enforced server-side (5)
  custom_cron?: string | null; // "custom"
  run_at?: string | null; // ISO datetime — "once"
}

export interface Clarification {
  question: string;
  answer: string;
}

export interface SchedulePublic {
  id: string;
  organization_id: string;
  created_by: string;
  name: string;
  description?: string | null;
  target_type?: 'agent' | 'orchestration';
  agent_id?: string | null;
  orchestration_id?: string | null;
  message: string;
  clarifications: Clarification[];
  thread_id: string;
  recurrence: RecurrenceConfig;
  cron_expr?: string | null;
  timezone: string;
  status: "active" | "paused" | "running" | "completed" | "terminated";
  next_run_at: string;
  last_run_at?: string | null;
  last_run_status?: "success" | "failed" | null;
  last_run_error?: string | null;
  consecutive_failure_count: number;
  max_consecutive_failures: number;
  run_count: number;
  needs_attention: boolean;
  created_at: string;
  updated_at: string;
}

export interface ScheduleCreate {
  name: string;
  description?: string;
  target_type?: 'agent' | 'orchestration';
  agent_id?: string;
  orchestration_id?: string;
  message: string;
  clarifications?: Clarification[];
  recurrence: RecurrenceConfig;
  timezone: string;
  max_consecutive_failures?: number;
}

export interface ScheduleUpdate {
  name?: string;
  description?: string;
  message?: string;
  clarifications?: Clarification[];
  recurrence?: RecurrenceConfig;
  timezone?: string;
  max_consecutive_failures?: number;
  status?: "active" | "paused";
}

export interface ScheduleRunPublic {
  run_id: string;
  schedule_id: string;
  target_type?: 'agent' | 'orchestration';
  agent_id?: string | null;
  orchestration_id?: string | null;
  thread_id: string;
  status: "running" | "success" | "failed";
  attempt: number;
  message_sent: string;
  reply?: string | null;
  auth_errors: Record<string, string | null>[];
  error_type?: string | null;
  error_message?: string | null;
  started_at: string;
  completed_at?: string | null;
  duration_ms?: number | null;
}

export interface PreviewQuestionsResponse {
  questions: string[];
  is_capable?: boolean;
  invalid_reason?: string | null;
}

export interface ConnectorPermissions {
  write?: boolean;
  read?: boolean;
  delete?: boolean;
  payment?: boolean;
  [key: string]: boolean | undefined;
}

export interface AgentPermissionsDoc {
  id?: string;
  agent_id: string;
  organization_id: string;
  permissions: {
    tools?: Record<string, boolean>;
    connectors?: Record<string, ConnectorPermissions>;
  };
  created_at: string;
  updated_at: string;
}

export interface AgentPermissionsPatch {
  tools?: Record<string, boolean>;
  connectors?: Record<string, ConnectorPermissions>;
}
