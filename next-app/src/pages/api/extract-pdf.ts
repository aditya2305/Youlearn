// pages/api/extract-pdf.ts
import type { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method === 'POST') {
    try {
      const { pdfUrl } = req.body;
      
      if (!pdfUrl) {
        return res.status(400).json({ error: 'Missing PDF URL' });
      }

      const response = await fetch(`${BACKEND_URL}/extract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pdf_url: pdfUrl })
      });

      const data = await response.json();
      
      if (!response.ok) {
        return res.status(response.status).json(data);
      }

      return res.status(200).json(data);
    } catch (error: any) {
      return res.status(500).json({ 
        error: 'Extraction failed',
        details: error.message 
      });
    }
  }

  return res.status(405).json({ error: 'Method not allowed' });
}
