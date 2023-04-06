INSERT INTO pavao.account (login, first_name) VALUES ('system', 'System');

INSERT INTO pavao.class (name) VALUES ('Administrator');

INSERT INTO pavao.account ( login, first_name, last_name) VALUES ( 'gustavo.venturini', 'Gustavo', 'Venturini');

INSERT INTO pavao.assignment ( account, class) SELECT acc.id, cls.id FROM pavao.account acc CROSS JOIN pavao.class cls WHERE acc.login = 'gustavo.venturini' AND cls.name = 'Administrator';

INSERT INTO pavao.authentication ( account, hash, active, needs_change, last_login) SELECT id, '$argon2id$v=19$m=65536,t=3,p=4$LCMDNNOXLzyk9z8tZysbng$l81v97JmiQoxOMSdPeIEG26oesl1sbZ89HY2RlDsRow', TRUE, FALSE, CURRENT_TIMESTAMP() FROM pavao.account WHERE login = 'gustavo.venturini';
