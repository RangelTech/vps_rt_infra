# scripts/infisical

Ferramentas da fundação de segredos (spec 57, §0A). **Nenhum valor de segredo fica neste repositório.**

- : cliente mínimo da API do Infisical (login Universal Auth). A credencial vem de um arquivo **fora do repositório** (; padrão: o cofre pessoal em ).
- : copia o  de um produto da VPS () para o Infisical (projeto , ambiente , pasta ) **sem trocar nenhum valor** (R5), confere **1 a 1** e grava um relatório de evidência (só nomes, nunca valores). Não sobrescreve segredo que já existe. Sai com erro se alguma variável não bater.

Uso: 
