// pages/api/extract-pdf.ts
import type { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export const config = {
  api: {
    bodyParser: {
      sizeLimit: '10mb',
    },
    responseLimit: false, // Disable response size limit for streaming
  },
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method === 'POST') {
    try {
      const { pdfUrl } = req.body;
      
      if (!pdfUrl) {
        return res.status(400).json({ error: 'Missing PDF URL' });
      }

      // Forward the streaming response from backend
      const response = await fetch(`${BACKEND_URL}/extract`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ pdf_url: pdfUrl }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        return res.status(response.status).json(errorData);
      }

      // Set up streaming response
      res.setHeader('Content-Type', 'application/json');
      res.setHeader('Transfer-Encoding', 'chunked');

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No reader available');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        // Forward the chunk to the client
        res.write(value);
      }

      res.end();
    } catch (error: any) {
      return res.status(500).json({ 
        error: 'Extraction failed',
        details: error.message 
      });
    }
  }

  return res.status(405).json({ error: 'Method not allowed' });
}
