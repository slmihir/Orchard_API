'use client';

import { useState, useEffect } from 'react';
import {
  Eye,
  EyeOff,
  FileText,
  FormInput,
  Tag,
  Link,
  Globe,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Step, AssertionStepType, AssertionConfig, AssertionOperator } from '@/types';
import { cn } from '@/lib/utils';

interface AssertionEditorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  step?: Step;  // If provided, editing existing step
  onSave: (step: Partial<Step>) => void;
}

const assertionTypes: { type: AssertionStepType; label: string; icon: React.ReactNode; description: string }[] = [
  { type: 'assert_visible', label: 'Visible', icon: <Eye className="w-4 h-4" />, description: 'Element is visible on page' },
  { type: 'assert_hidden', label: 'Hidden', icon: <EyeOff className="w-4 h-4" />, description: 'Element is not visible' },
  { type: 'assert_text', label: 'Text', icon: <FileText className="w-4 h-4" />, description: 'Element contains text' },
  { type: 'assert_value', label: 'Value', icon: <FormInput className="w-4 h-4" />, description: 'Input has value' },
  { type: 'assert_attribute', label: 'Attribute', icon: <Tag className="w-4 h-4" />, description: 'Element attribute check' },
  { type: 'assert_url', label: 'URL', icon: <Link className="w-4 h-4" />, description: 'Current URL matches' },
  { type: 'assert_api', label: 'API', icon: <Globe className="w-4 h-4" />, description: 'API response check' },
];

const operators: { value: AssertionOperator; label: string }[] = [
  { value: 'equals', label: 'equals' },
  { value: 'contains', label: 'contains' },
  { value: 'matches', label: 'matches (regex)' },
  { value: 'not_equals', label: 'not equals' },
  { value: 'not_contains', label: 'not contains' },
];

export function AssertionEditor({ open, onOpenChange, step, onSave }: AssertionEditorProps) {
  const [assertionType, setAssertionType] = useState<AssertionStepType>('assert_visible');
  const [selector, setSelector] = useState('');
  const [expected, setExpected] = useState('');
  const [operator, setOperator] = useState<AssertionOperator>('equals');
  const [attribute, setAttribute] = useState('');
  const [apiMethod, setApiMethod] = useState('GET');
  const [apiUrlPattern, setApiUrlPattern] = useState('');
  const [apiStatus, setApiStatus] = useState('200');
  const [apiBodyContains, setApiBodyContains] = useState('');

  useEffect(() => {
    if (step) {
      setAssertionType(step.type as AssertionStepType);
      setSelector(step.selector || '');
      const config = step.assertion_config || {};
      setExpected(config.expected || '');
      setOperator(config.operator || 'equals');
      setAttribute(config.attribute || '');
      setApiMethod(config.api_method || 'GET');
      setApiUrlPattern(config.api_url_pattern || '');
      setApiStatus(String(config.api_status || 200));
      setApiBodyContains(config.api_body_contains || '');
    } else {
      setAssertionType('assert_visible');
      setSelector('');
      setExpected('');
      setOperator('equals');
      setAttribute('');
      setApiMethod('GET');
      setApiUrlPattern('');
      setApiStatus('200');
      setApiBodyContains('');
    }
  }, [step, open]);

  const handleSave = () => {
    const config: AssertionConfig = {};

    if (['assert_text', 'assert_value', 'assert_attribute', 'assert_url'].includes(assertionType)) {
      config.expected = expected;
      config.operator = operator;
    }

    if (assertionType === 'assert_attribute') {
      config.attribute = attribute;
    }

    if (assertionType === 'assert_api') {
      config.api_method = apiMethod;
      config.api_url_pattern = apiUrlPattern;
      config.api_status = parseInt(apiStatus) || 200;
      if (apiBodyContains) {
        config.api_body_contains = apiBodyContains;
      }
    }

    onSave({
      id: step?.id,
      type: assertionType,
      selector: assertionType !== 'assert_url' && assertionType !== 'assert_api' ? selector : undefined,
      assertion_config: Object.keys(config).length > 0 ? config : undefined,
      timestamp: step?.timestamp || new Date().toISOString(),
    });

    onOpenChange(false);
  };

  const needsSelector = !['assert_url', 'assert_api'].includes(assertionType);
  const needsExpected = ['assert_text', 'assert_value', 'assert_attribute', 'assert_url'].includes(assertionType);
  const needsAttribute = assertionType === 'assert_attribute';
  const needsApiConfig = assertionType === 'assert_api';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{step ? 'Edit Assertion' : 'Add Assertion'}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Assertion Type Selector */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Assertion Type</label>
            <div className="grid grid-cols-4 gap-2">
              {assertionTypes.map((at) => (
                <button
                  key={at.type}
                  onClick={() => setAssertionType(at.type)}
                  className={cn(
                    'flex flex-col items-center gap-1 p-3 rounded-lg border text-xs transition-colors',
                    assertionType === at.type
                      ? 'border-emerald-500 bg-emerald-500/10 text-emerald-500'
                      : 'border-border hover:bg-muted'
                  )}
                >
                  {at.icon}
                  <span>{at.label}</span>
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              {assertionTypes.find((a) => a.type === assertionType)?.description}
            </p>
          </div>

          {/* Selector Input */}
          {needsSelector && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Element Selector</label>
              <Input
                value={selector}
                onChange={(e) => setSelector(e.target.value)}
                placeholder="#my-element, .class-name, or [data-testid='value']"
                className="font-mono text-sm"
              />
            </div>
          )}

          {/* Attribute Name (for assert_attribute) */}
          {needsAttribute && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Attribute Name</label>
              <Input
                value={attribute}
                onChange={(e) => setAttribute(e.target.value)}
                placeholder="e.g., disabled, href, class"
              />
            </div>
          )}

          {/* Operator + Expected Value */}
          {needsExpected && (
            <div className="grid grid-cols-3 gap-2">
              <div className="space-y-2">
                <label className="text-sm font-medium">Operator</label>
                <select
                  value={operator}
                  onChange={(e) => setOperator(e.target.value as AssertionOperator)}
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  {operators.map((op) => (
                    <option key={op.value} value={op.value}>
                      {op.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="col-span-2 space-y-2">
                <label className="text-sm font-medium">Expected Value</label>
                <Input
                  value={expected}
                  onChange={(e) => setExpected(e.target.value)}
                  placeholder="Expected text or value"
                />
              </div>
            </div>
          )}

          {/* API Config */}
          {needsApiConfig && (
            <div className="space-y-3 p-3 rounded-lg bg-muted/30 border">
              <div className="grid grid-cols-3 gap-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Method</label>
                  <select
                    value={apiMethod}
                    onChange={(e) => setApiMethod(e.target.value)}
                    className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                  >
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="PATCH">PATCH</option>
                    <option value="DELETE">DELETE</option>
                  </select>
                </div>
                <div className="col-span-2 space-y-2">
                  <label className="text-sm font-medium">URL Pattern</label>
                  <Input
                    value={apiUrlPattern}
                    onChange={(e) => setApiUrlPattern(e.target.value)}
                    placeholder="/api/users or partial match"
                    className="font-mono text-sm"
                  />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Status Code</label>
                  <Input
                    value={apiStatus}
                    onChange={(e) => setApiStatus(e.target.value)}
                    placeholder="200"
                    type="number"
                  />
                </div>
                <div className="col-span-2 space-y-2">
                  <label className="text-sm font-medium">Body Contains (optional)</label>
                  <Input
                    value={apiBodyContains}
                    onChange={(e) => setApiBodyContains(e.target.value)}
                    placeholder="Expected text in response"
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            className="bg-emerald-600 hover:bg-emerald-700"
            disabled={needsSelector && !selector}
          >
            {step ? 'Update Assertion' : 'Add Assertion'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
