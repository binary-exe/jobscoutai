'use client';

import { useMemo } from 'react';

interface FormattedDescriptionProps {
  text: string;
  className?: string;
}

/**
 * Formats plain text job descriptions into readable, structured content.
 * Detects common patterns like bullet points, headings, and paragraphs.
 */
export function FormattedDescription({ text, className = '' }: FormattedDescriptionProps) {
  const formatted = useMemo(() => {
    if (!text) return '';

    // Split into lines and process
    let lines = text.split(/\r?\n/);
    
    // Clean up lines
    lines = lines.map(line => line.trim()).filter(line => line.length > 0);
    
    // Detect patterns and format
    const formattedLines: string[] = [];
    let inList = false;
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const nextLine = i < lines.length - 1 ? lines[i + 1] : '';
      
      // Detect headings (lines that are short and end without punctuation, or contain ":" and are short)
      const isHeading = (line.length < 80 && (
        line.endsWith(':') ||
        /^(Requirements|Benefits|Responsibilities|Qualifications|About|Overview|Description|Location|Salary|Company|What|Why|How|When|Where)/i.test(line)
      ));
      
      // Detect bullet points (starts with bullet, dash, asterisk, or number)
      const bulletMatch = line.match(/^[•\-\*]\s+(.+)$/) || 
                         line.match(/^(\d+[\.\)])\s+(.+)$/) ||
                         line.match(/^[-]\s+(.+)$/);
      
      // Detect list items (short lines that might be bullets)
      const isListItem = bulletMatch || 
                        (line.length < 120 && 
                         !line.endsWith('.') && 
                         !line.endsWith('!') && 
                         !line.endsWith('?') &&
                         !isHeading &&
                         (nextLine === '' || nextLine.match(/^[•\-\*]/) || nextLine.length < 120));
      
      if (isHeading) {
        if (inList) {
          formattedLines.push('</ul>');
          inList = false;
        }
        formattedLines.push(`<h3>${escapeHtml(line.replace(/:$/, ''))}</h3>`);
      } else if (bulletMatch) {
        if (!inList) {
          formattedLines.push('<ul>');
          inList = true;
        }
        const content = bulletMatch[2] || bulletMatch[1] || line;
        formattedLines.push(`<li>${escapeHtml(content)}</li>`);
      } else if (isListItem && !line.includes('http')) {
        if (!inList) {
          formattedLines.push('<ul>');
          inList = true;
        }
        formattedLines.push(`<li>${escapeHtml(line)}</li>`);
      } else {
        if (inList) {
          formattedLines.push('</ul>');
          inList = false;
        }
        // Regular paragraph
        formattedLines.push(`<p>${escapeHtml(line)}</p>`);
      }
    }
    
    if (inList) {
      formattedLines.push('</ul>');
    }
    
    return formattedLines.join('\n');
  }, [text]);

  return (
    <div 
      className={`prose prose-sm max-w-none text-foreground ${className}`}
      dangerouslySetInnerHTML={{ __html: formatted }}
      style={{
        lineHeight: '1.7',
      }}
    />
  );
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
