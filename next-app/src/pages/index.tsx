import { useState, useCallback, useRef, useEffect } from 'react';
import dynamic from 'next/dynamic';
import TranscriptPanel from '@/components/TranscriptPanel';

const PdfViewerDynamic = dynamic(() => import('@/components/PdfViewer'), { ssr: false });

interface ExtractedText {
  text: string;
  bbox: number[];
  page_num: number;
}

export default function Home() {
  const [pdfUrl, setPdfUrl] = useState('');
  const [extractedText, setExtractedText] = useState<ExtractedText[]>([]);
  const [selectedBBox, setSelectedBBox] = useState<number[] | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [processingProgress, setProcessingProgress] = useState(0);
  const batchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pendingUpdatesRef = useRef<ExtractedText[]>([]);

  const batchUpdateText = useCallback((newTexts: ExtractedText[]) => {
    pendingUpdatesRef.current = [...pendingUpdatesRef.current, ...newTexts];

    // Clear existing timeout
    if (batchTimeoutRef.current) {
      clearTimeout(batchTimeoutRef.current);
    }

    // Set new timeout to batch updates
    batchTimeoutRef.current = setTimeout(() => {
      setExtractedText(current => [...current, ...pendingUpdatesRef.current]);
      pendingUpdatesRef.current = [];
    }, 500); // Adjust this delay as needed
  }, []);

  // Clean up timeout on unmount
  useEffect(() => {
    return () => {
      if (batchTimeoutRef.current) {
        clearTimeout(batchTimeoutRef.current);
      }
    };
  }, []);

  const handleExtract = async () => {
    if (!pdfUrl) {
      setError('Please enter a PDF URL');
      return;
    }
    setLoading(true);
    setError('');
    setExtractedText([]);
    setProcessingProgress(0);

    try {
      const response = await fetch('/api/extract-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pdfUrl })
      });

      if (!response.ok) {
        throw new Error('Extraction failed');
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No reader available');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        for (let i = 0; i < lines.length - 1; i++) {
          const line = lines[i].trim();
          if (!line) continue;

          try {
            const data = JSON.parse(line);
            
            if (data.type === 'progress') {
              const progress = (data.processed_pages / data.total_pages) * 100;
              setProcessingProgress(Math.round(progress));
            } else if (data.type === 'data') {
              if (data.extracted_data?.length > 0) {
                batchUpdateText(data.extracted_data);
              }
              if (data.is_complete) {
                setLoading(false);
              }
            }
          } catch (e) {
            console.error('Error parsing JSON:', e);
          }
        }
        
        buffer = lines[lines.length - 1];
      }

      // Process any remaining data
      if (buffer.trim()) {
        try {
          const data = JSON.parse(buffer);
          if (data.type === 'data' && data.extracted_data?.length > 0) {
            batchUpdateText(data.extracted_data);
          }
        } catch (e) {
          console.error('Error parsing final JSON:', e);
        }
      }

      setError('');
    } catch (err: any) {
      setError(err.message);
      setLoading(false);
    }
  };

  const handleTextClick = (bbox: number[], pageNum: number) => {
    setSelectedBBox(bbox);
    setCurrentPage(pageNum);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-[1800px] mx-auto">
        {/* Input Section */}
        <div className="mb-6 bg-white rounded-lg shadow p-4">
          <div className="flex gap-4">
            <input
              type="text"
              value={pdfUrl}
              onChange={(e) => setPdfUrl(e.target.value)}
              placeholder="Enter PDF URL"
              className="flex-1 p-2 border rounded"
            />
            <button
              onClick={handleExtract}
              disabled={loading}
              className={`px-6 py-2 bg-blue-600 text-white rounded ${
                loading ? 'opacity-50' : 'hover:bg-blue-700'
              }`}
            >
              {loading ? 'Processing...' : 'Extract Text'}
            </button>
          </div>
          {error && <p className="text-red-500 mt-2">{error}</p>}
        </div>

        {pdfUrl && (
          <div className="grid grid-cols-3 gap-6">
            <div className="col-span-2">
              <PdfViewerDynamic
                url={pdfUrl}
                currentPage={currentPage}
                selectedBBox={selectedBBox}
                onPageChange={setCurrentPage}
              />
            </div>
            <div className="col-span-1">
              <TranscriptPanel
                extractedText={extractedText}
                onTextClick={handleTextClick}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
