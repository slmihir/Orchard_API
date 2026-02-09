'use client';

import { useRef, useEffect, useState } from 'react';
import { Send, Sparkles, Bot, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useChatStore } from '@/stores/chatStore';
import { cn } from '@/lib/utils';

interface ChatPanelProps {
  onSendMessage: (message: string) => void;
}

export function ChatPanel({ onSendMessage }: ChatPanelProps) {
  const { messages, isTyping } = useChatStore();
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      onSendMessage(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border/50">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 text-primary">
          <Sparkles className="w-4 h-4" />
        </div>
        <div>
          <h2 className="text-sm font-semibold">AI Assistant</h2>
          <p className="text-xs text-muted-foreground">Describe your test flow</p>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 px-4">
        <div className="py-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
                <Bot className="w-6 h-6 text-primary" />
              </div>
              <h3 className="text-sm font-medium mb-1">Start a conversation</h3>
              <p className="text-xs text-muted-foreground max-w-[200px]">
                Describe the test flow you want to automate
              </p>
              <div className="mt-6 space-y-2 w-full">
                {[
                  'Test login flow on example.com',
                  'Add item to cart and checkout',
                  'Fill out contact form',
                ].map((suggestion, i) => (
                  <button
                    key={i}
                    onClick={() => setInput(suggestion)}
                    className="w-full px-3 py-2 text-xs text-left rounded-lg border border-border/50 hover:border-primary/50 hover:bg-primary/5 transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message, index) => (
            <div
              key={message.id}
              className={cn(
                'message-animate flex gap-3',
                message.role === 'user' ? 'flex-row-reverse' : ''
              )}
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <div
                className={cn(
                  'flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center',
                  message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground'
                )}
              >
                {message.role === 'user' ? (
                  <User className="w-3.5 h-3.5" />
                ) : (
                  <Bot className="w-3.5 h-3.5" />
                )}
              </div>
              <div
                className={cn(
                  'max-w-[85%] px-3 py-2 rounded-lg text-sm overflow-hidden',
                  message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted/50'
                )}
              >
                <p className="whitespace-pre-wrap break-words">{message.content}</p>
              </div>
            </div>
          ))}

          {isTyping && (
            <div className="flex gap-3 message-animate">
              <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-muted text-muted-foreground flex items-center justify-center">
                <Bot className="w-3.5 h-3.5" />
              </div>
              <div className="px-3 py-2 rounded-lg bg-muted/50">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground typing-dot" />
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground typing-dot" />
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground typing-dot" />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-border/50">
        <div className="relative">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe what you want to test..."
            className="min-h-[80px] max-h-[160px] pr-12 resize-none bg-muted/30 border-border/50 focus:border-primary"
            rows={3}
          />
          <Button
            type="submit"
            size="icon"
            disabled={!input.trim()}
            className="absolute bottom-2 right-2 h-8 w-8"
          >
            <Send className="w-4 h-4" />
          </Button>
        </div>
        <p className="mt-2 text-[10px] text-muted-foreground text-center">
          Press Enter to send, Shift+Enter for new line
        </p>
      </form>
    </div>
  );
}
