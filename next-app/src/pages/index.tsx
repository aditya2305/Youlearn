import { useState } from 'react';
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

  const handleExtract = async () => {
    if (!pdfUrl) {
      setError('Please enter a PDF URL');
      return;
    }
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/extract-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pdfUrl }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Extraction failed');
      }
      const data = await response.json();
      setExtractedText(data.extracted_data);
    } catch (err: any) {
      setError(err.message);
    } finally {
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
