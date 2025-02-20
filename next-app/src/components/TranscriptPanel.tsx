import React, { memo } from 'react';
import { FixedSizeList as List } from 'react-window';

interface TextChunk {
  text: string;
  bbox: number[]; 
  page_num: number; 
}

interface TranscriptPanelProps {
  extractedText: TextChunk[];
  onTextClick: (bbox: number[], pageNum: number) => void;
}

// Memoize the Row component to prevent unnecessary re-renders
const Row = memo(({ data, index, style }: { 
  data: { items: TextChunk[], onTextClick: (bbox: number[], pageNum: number) => void },
  index: number, 
  style: React.CSSProperties 
}) => {
  const chunk = data.items[index];
  return (
    <div
      style={style}
      onClick={() => data.onTextClick(chunk.bbox, chunk.page_num)}
      className="p-3 bg-gray-50 hover:bg-blue-50 cursor-pointer transition-colors duration-150 m-1 rounded"
    >
      <p className="text-gray-800">{chunk.text}</p>
      <span className="text-xs text-gray-500">
        Page {chunk.page_num}
      </span>
    </div>
  );
});

Row.displayName = 'Row';

const TranscriptPanel: React.FC<TranscriptPanelProps> = ({
  extractedText,
  onTextClick,
}) => {
  // Memoize the items data to prevent unnecessary re-renders
  const itemData = React.useMemo(() => ({
    items: extractedText,
    onTextClick,
  }), [extractedText, onTextClick]);

  return (
    <div className="h-[800px] bg-white rounded-lg shadow overflow-hidden">
      <div className="p-4 border-b bg-gray-50">
        <h2 className="text-xl font-bold text-gray-800">Transcript</h2>
      </div>
      <div className="h-[calc(100%-4rem)]">
        {extractedText?.length === 0 ? (
          <p className="text-gray-500 text-center p-4">No extracted text available</p>
        ) : (
          <List
            height={700}
            itemCount={extractedText.length}
            itemSize={80}
            width="100%"
            itemData={itemData}
          >
            {Row}
          </List>
        )}
      </div>
    </div>
  );
};

export default memo(TranscriptPanel);
