-- MySQL dump 10.13  Distrib 8.0.46, for Linux (x86_64)
--
-- Host: localhost    Database: mygames_dev
-- ------------------------------------------------------
-- Server version	8.0.46-0ubuntu0.24.04.3

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `avaliacoes_manuais`
--

DROP TABLE IF EXISTS `avaliacoes_manuais`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `avaliacoes_manuais` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nome_produto_informado` varchar(255) NOT NULL,
  `descricao_estado` text,
  `email_contato` varchar(150) NOT NULL,
  `data_solicitacao` datetime DEFAULT CURRENT_TIMESTAMP,
  `status` enum('Pendente','Avaliado','Recusado') DEFAULT 'Pendente',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `canais_aquisicao`
--

DROP TABLE IF EXISTS `canais_aquisicao`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `canais_aquisicao` (
  `id` int NOT NULL AUTO_INCREMENT,
  `slug_tecnico` varchar(50) NOT NULL,
  `nome_exibicao` varchar(100) NOT NULL,
  `ativo` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `slug_tecnico` (`slug_tecnico`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `catalogo_mestre`
--

DROP TABLE IF EXISTS `catalogo_mestre`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `catalogo_mestre` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nome_produto` varchar(255) NOT NULL,
  `categoria_id` int DEFAULT NULL,
  `plataforma` varchar(50) DEFAULT NULL,
  `valor_venda_ref` decimal(10,2) DEFAULT NULL,
  `valor_pix_base` decimal(10,2) DEFAULT NULL,
  `valor_cred_base` decimal(10,2) DEFAULT NULL,
  `foto_oficial_url` varchar(255) DEFAULT NULL,
  `sku_interno` varchar(50) DEFAULT NULL,
  `ativo` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `sku_interno` (`sku_interno`),
  UNIQUE KEY `sku_interno_2` (`sku_interno`),
  KEY `fk_catalogo_categoria` (`categoria_id`),
  CONSTRAINT `fk_catalogo_categoria` FOREIGN KEY (`categoria_id`) REFERENCES `categorias` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=96 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `categorias`
--

DROP TABLE IF EXISTS `categorias`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `categorias` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nome` varchar(50) NOT NULL,
  `ativo` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `categorias_avaliacao`
--

DROP TABLE IF EXISTS `categorias_avaliacao`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `categorias_avaliacao` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nome_categoria` varchar(100) DEFAULT NULL,
  `slug` varchar(50) DEFAULT NULL,
  `categoria_id` int DEFAULT NULL,
  `obrigatorio` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`id`),
  KEY `fk_avaliacao_categoria` (`categoria_id`),
  CONSTRAINT `fk_avaliacao_categoria` FOREIGN KEY (`categoria_id`) REFERENCES `categorias` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `clientes_usuarios`
--

DROP TABLE IF EXISTS `clientes_usuarios`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `clientes_usuarios` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nome_completo` varchar(255) NOT NULL,
  `email` varchar(150) NOT NULL,
  `whatsapp` varchar(20) DEFAULT NULL,
  `cidade` varchar(100) DEFAULT NULL,
  `estado_nome` varchar(100) DEFAULT NULL,
  `estado_uf` char(2) DEFAULT NULL,
  `origem_lead` varchar(50) DEFAULT 'Direto',
  `cpf` varchar(14) DEFAULT NULL,
  `chave_pix` varchar(100) DEFAULT NULL,
  `cep` varchar(9) DEFAULT NULL,
  `endereco` varchar(255) DEFAULT NULL,
  `numero` varchar(20) DEFAULT NULL,
  `complemento` varchar(100) DEFAULT NULL,
  `bairro` varchar(100) DEFAULT NULL,
  `data_cadastro` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=80 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dados_empresa`
--

DROP TABLE IF EXISTS `dados_empresa`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dados_empresa` (
  `id` int NOT NULL AUTO_INCREMENT,
  `razao_social` varchar(150) NOT NULL,
  `nome_fantasia` varchar(150) NOT NULL,
  `cnpj` varchar(20) NOT NULL,
  `cep` varchar(10) NOT NULL,
  `logradouro` varchar(150) NOT NULL,
  `numero` varchar(20) NOT NULL,
  `complemento` varchar(100) DEFAULT NULL,
  `bairro` varchar(100) NOT NULL,
  `cidade` varchar(100) NOT NULL,
  `estado_uf` char(2) NOT NULL,
  `telefone_contato` varchar(20) DEFAULT NULL,
  `email_contato` varchar(150) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `feedbacks_recusa`
--

DROP TABLE IF EXISTS `feedbacks_recusa`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `feedbacks_recusa` (
  `id` int NOT NULL AUTO_INCREMENT,
  `sessao_uuid` varchar(50) NOT NULL,
  `motivo_texto` text,
  `cidade_informada` varchar(100) DEFAULT NULL,
  `estado_uf` varchar(2) DEFAULT NULL,
  `canal_aquisicao` varchar(50) DEFAULT NULL,
  `valor_oferta_recusada` decimal(10,2) DEFAULT NULL,
  `itens_carrinho_json` json DEFAULT NULL,
  `user_agent` varchar(255) DEFAULT NULL,
  `ip_origem` varchar(45) DEFAULT NULL,
  `data_recusa` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=26 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `historico_status_protocolo`
--

DROP TABLE IF EXISTS `historico_status_protocolo`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `historico_status_protocolo` (
  `id` int NOT NULL AUTO_INCREMENT,
  `protocolo_id` int NOT NULL,
  `status_id` int NOT NULL,
  `usuario_admin_id` int NOT NULL,
  `data_alteracao` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_historico_protocolo` (`protocolo_id`),
  KEY `fk_historico_status` (`status_id`),
  KEY `fk_historico_usuario` (`usuario_admin_id`),
  CONSTRAINT `fk_historico_protocolo` FOREIGN KEY (`protocolo_id`) REFERENCES `protocolos_recompra` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_historico_status` FOREIGN KEY (`status_id`) REFERENCES `status_protocolos` (`id`),
  CONSTRAINT `fk_historico_usuario` FOREIGN KEY (`usuario_admin_id`) REFERENCES `usuarios_admin` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=170 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `itens_periciados`
--

DROP TABLE IF EXISTS `itens_periciados`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `itens_periciados` (
  `id` int NOT NULL AUTO_INCREMENT,
  `protocolo_id` int DEFAULT NULL,
  `produto_id` int DEFAULT NULL,
  `status_laudo_id` tinyint DEFAULT NULL,
  `recebido_fisicamente` tinyint(1) DEFAULT NULL,
  `qtd_declarada` int DEFAULT '1',
  `qtd_recebida` int DEFAULT '0',
  `fotos_json` json DEFAULT NULL,
  `comentarios` text,
  `motivo_recusa` text,
  `data_pericia` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `valor_pix_unitario` decimal(10,2) DEFAULT NULL,
  `valor_cred_unitario` decimal(10,2) DEFAULT NULL,
  `valor_final_pix` decimal(10,2) DEFAULT NULL COMMENT 'Valor final aprovado na perícia técnica (Pix)',
  `valor_final_credito` decimal(10,2) DEFAULT NULL COMMENT 'Valor final aprovado na perícia técnica (Crédito)',
  PRIMARY KEY (`id`),
  KEY `protocolo_id` (`protocolo_id`),
  KEY `produto_id` (`produto_id`)
) ENGINE=InnoDB AUTO_INCREMENT=295 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `opcoes_estado`
--

DROP TABLE IF EXISTS `opcoes_estado`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `opcoes_estado` (
  `id` int NOT NULL AUTO_INCREMENT,
  `categoria_id` int DEFAULT NULL,
  `descricao` varchar(255) DEFAULT NULL,
  `fator_depreciacao` decimal(5,2) DEFAULT NULL,
  `valor_fixo_extra` decimal(10,2) DEFAULT '0.00',
  `exibir_ordem` int DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `categoria_id` (`categoria_id`)
) ENGINE=InnoDB AUTO_INCREMENT=48 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `perguntas_conservacao`
--

DROP TABLE IF EXISTS `perguntas_conservacao`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `perguntas_conservacao` (
  `id` int NOT NULL AUTO_INCREMENT,
  `categoria_id` int NOT NULL,
  `texto_pergunta` varchar(255) NOT NULL,
  `tipo_resposta` enum('Sim/Nao','Multipla_Escolha') NOT NULL,
  `impacto_valor` decimal(10,2) DEFAULT '0.00',
  PRIMARY KEY (`id`),
  KEY `categoria_id` (`categoria_id`),
  CONSTRAINT `perguntas_conservacao_ibfk_1` FOREIGN KEY (`categoria_id`) REFERENCES `categorias` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `pericia_selecionada`
--

DROP TABLE IF EXISTS `pericia_selecionada`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pericia_selecionada` (
  `item_id` int NOT NULL,
  `opcao_id` int NOT NULL,
  PRIMARY KEY (`item_id`,`opcao_id`),
  KEY `opcao_id` (`opcao_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `propostas_venda`
--

DROP TABLE IF EXISTS `propostas_venda`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `propostas_venda` (
  `id` int NOT NULL AUTO_INCREMENT,
  `usuario_id` int DEFAULT NULL,
  `produto_id` int DEFAULT NULL,
  `categoria_id` int NOT NULL,
  `quantidade` int DEFAULT '1',
  `observacoes` text,
  `fotos_caminho` varchar(500) DEFAULT NULL,
  `valor_preliminar` decimal(10,2) DEFAULT NULL,
  `status_avaliacao` enum('Pendente','Em Análise Física','Concluída') DEFAULT 'Pendente',
  `data_proposta` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `categoria_id` (`categoria_id`),
  CONSTRAINT `propostas_venda_ibfk_1` FOREIGN KEY (`categoria_id`) REFERENCES `categorias` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `protocolos_recompra`
--

DROP TABLE IF EXISTS `protocolos_recompra`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `protocolos_recompra` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cliente_id` int DEFAULT NULL,
  `numero_protocolo` varchar(20) DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `status` enum('Aberto','Aguardando Fotos','Aceito','Recusado','Finalizado') DEFAULT 'Aberto',
  `valor_total_pix` decimal(10,2) DEFAULT '0.00',
  `valor_total_credito` decimal(10,2) DEFAULT '0.00',
  `valor_avaliado` decimal(10,2) DEFAULT NULL,
  `qtd_caixas` int DEFAULT '1',
  `codigo_rastreio` varchar(50) DEFAULT NULL,
  `laudo_tecnico` text,
  `data_criacao` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `canal_aquisicao_id` int DEFAULT NULL,
  `e_ticket` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `numero_protocolo` (`numero_protocolo`),
  KEY `cliente_id` (`cliente_id`),
  KEY `fk_protocolos_canal_aquisicao` (`canal_aquisicao_id`),
  KEY `fk_protocolos_status` (`status_id`),
  CONSTRAINT `fk_protocolos_canal_aquisicao` FOREIGN KEY (`canal_aquisicao_id`) REFERENCES `canais_aquisicao` (`id`),
  CONSTRAINT `fk_protocolos_status` FOREIGN KEY (`status_id`) REFERENCES `status_protocolos` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=173 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `regioes_atendimento`
--

DROP TABLE IF EXISTS `regioes_atendimento`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `regioes_atendimento` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cidade` varchar(100) NOT NULL,
  `estado_uf` char(2) NOT NULL,
  `multiplicador_preco` decimal(4,2) DEFAULT '1.00',
  `ativo` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_cidade_uf` (`cidade`,`estado_uf`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `status_protocolos`
--

DROP TABLE IF EXISTS `status_protocolos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `status_protocolos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `slug_tecnico` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `nome_exibicao` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `cor_badge` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'secondary',
  `ativo` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `slug_tecnico` (`slug_tecnico`)
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `usuarios_admin`
--

DROP TABLE IF EXISTS `usuarios_admin`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `usuarios_admin` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nome_completo` varchar(150) NOT NULL,
  `usuario_login` varchar(50) NOT NULL,
  `email` varchar(150) NOT NULL,
  `senha_hash` varchar(255) NOT NULL,
  `nivel_acesso` enum('Administrador','Operador') DEFAULT 'Operador',
  `ativo` tinyint(1) DEFAULT '1',
  `data_criacao` datetime DEFAULT CURRENT_TIMESTAMP,
  `ultimo_login` datetime DEFAULT NULL,
  `requer_nova_senha` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `usuario_login` (`usuario_login`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-07-09 10:52:34
