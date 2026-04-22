export const metadata = {
  title: 'Secure Log Dashboard',
  description: 'Enterprise Log Monitoring System V1.0',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
