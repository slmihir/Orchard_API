// Action step types
export type ActionStepType = 'navigate' | 'click' | 'fill' | 'wait' | 'scroll' | 'hover';

// Assertion step types
export type AssertionStepType =
  | 'assert_visible'     // Element exists and is visible
  | 'assert_hidden'      // Element is not visible
  | 'assert_text'        // Element contains expected text
  | 'assert_value'       // Input has expected value
  | 'assert_attribute'   // Element has attribute value
  | 'assert_url'         // Current URL matches pattern
  | 'assert_api';        // API response validation

// Combined step types
export type StepType = ActionStepType | AssertionStepType;

// Comparison operators for assertions
export type AssertionOperator =
  | 'equals'
  | 'contains'
  | 'matches'
  | 'not_equals'
  | 'not_contains'
  | 'gt'
  | 'lt'
  | 'gte'
  | 'lte';

// Configuration for assertion steps
export interface AssertionConfig {
  expected?: string;              // Expected text/value
  operator?: AssertionOperator;   // Comparison operator
  attribute?: string;             // For assert_attribute (e.g., "disabled", "href")
  api_method?: string;            // GET, POST, etc. for assert_api
  api_url_pattern?: string;       // URL pattern to match for assert_api
  api_status?: number;            // Expected status code for assert_api
  api_body_contains?: string;     // Expected content in response body
}

// Assertion result returned during test run
export interface AssertionResult {
  passed: boolean;
  message: string;
  actual?: string;
}

export interface Step {
  id: string;
  type: StepType;
  selector?: string;
  value?: string;
  screenshot?: string;
  timestamp: string;
  assertion_config?: AssertionConfig;
  // Populated during test run
  assertion_result?: AssertionResult;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

export interface Test {
  id: string;
  name: string;
  description?: string;
  targetUrl: string;
  createdAt: string;
  updatedAt: string;
  latestVersion?: TestVersion;
}

export interface TestVersion {
  id: string;
  versionNumber: number;
  createdAt: string;
  steps: Step[];
}

export interface Run {
  id: string;
  versionId: string;
  status: 'running' | 'passed' | 'failed';
  startedAt: string;
  finishedAt?: string;
  errorMessage?: string;
}

export type BrowserStatus = 'idle' | 'starting' | 'running' | 'stopped' | 'error';

export interface BrowserState {
  status: BrowserStatus;
  screenshot?: string;
  currentUrl?: string;
}

export type WebSocketMessageType =
  | 'chat'
  | 'status'
  | 'screenshot'
  | 'action'
  | 'complete'
  | 'error';

export interface WebSocketMessage {
  type: WebSocketMessageType;
  data: Record<string, unknown>;
}
