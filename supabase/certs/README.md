# Supabase production CA

`prod-ca-2021.crt` is a public CA certificate, not a private credential.
It was retrieved over verified HTTPS from:

https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt

The URL is the production expansion of `ssl:certificate_url` in Supabase's
[official dashboard configuration](https://github.com/supabase/supabase/blob/master/apps/studio/hooks/custom-content/custom-content.json).
The dashboard selects `prod` for its production environment in
[SSLConfiguration.tsx](https://github.com/supabase/supabase/blob/master/apps/studio/components/interfaces/Settings/Database/SSLConfiguration.tsx).

SHA-256 fingerprint:
`80:70:25:AD:50:D4:ED:21:9D:2C:9C:7D:29:9C:00:4F:82:4E:B0:0C:F7:F6:5A:FE:F6:07:D0:7B:72:E6:CA:FA`

Valid until 2031-04-26. Used only for this application's PostgreSQL connection
with `sslmode=verify-full`; no system trust store is changed. Obtain any replacement
through an authenticated official HTTPS source, never by trusting a certificate
presented by an unverified database endpoint alone.
